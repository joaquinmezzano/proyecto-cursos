import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean

import requests
import streamlit as st


FLOWABLE_URL = os.getenv(
    "FLOWABLE_URL",
    "http://localhost:8080/flowable-ui/process-api",
).rstrip("/")

PROCESS_KEY = "Process_Curso"
HISTORIAL_PROCESOS = "history/historic-process-instances"
HISTORIAL_VARIABLES = "history/historic-variable-instances"
HISTORIAL_ACTIVIDADES = "history/historic-activity-instances"
HISTORIAL_TAREAS = "history/historic-task-instances"

RESULTADOS = {
    "FINALIZADO": "Curso finalizado",
    "CANCELADO": "Cancelación",
    "RECHAZADO": "Rechazo de la propuesta",
    "NO_VIABLE": "Solicitud no viable",
    "SIN_RESPUESTA": "Cierre por falta de respuesta",
}
GRUPOS = {
    "administracion": "Administración",
    "docentes": "Docentes",
}
RAMAS = ("Inscripciones", "Materiales", "Recursos")
ACTIVIDADES_RECURSOS = ("Aula", "Virtual", "Equipo")


def listar(sesion, ruta, **filtros):
    """Recorre todas las páginas de una consulta REST de Flowable."""
    inicio = 0

    while True:
        respuesta = sesion.get(
            f"{FLOWABLE_URL}/{ruta}",
            params={**filtros, "start": inicio, "size": 100},
            timeout=20,
        )
        respuesta.raise_for_status()

        pagina = respuesta.json()
        filas = pagina["data"]
        yield from filas

        inicio += len(filas)
        if inicio >= pagina["total"]:
            return
        if not filas:
            raise RuntimeError(f"Flowable devolvió una página vacía en {ruta}.")


def calcular_resultados(sesion, instancias):
    """4.3.1. Cuenta los resultados sobre todas las instancias terminadas."""
    terminadas = {
        instancia["id"]
        for instancia in instancias
        if instancia.get("endTime")
    }

    resultados_por_id = {}
    if terminadas:
        for registro in listar(
            sesion,
            HISTORIAL_VARIABLES,
            variableName="resultado",
            excludeTaskVariables="true",
        ):
            instancia_id = registro.get("processInstanceId")
            if instancia_id in terminadas:
                valor = registro["variable"].get("value")
                if isinstance(valor, str) and valor in RESULTADOS:
                    resultados_por_id[instancia_id] = valor

    total = len(terminadas)
    conteos = Counter(resultados_por_id.values())
    cantidades = [
        (etiqueta, conteos[codigo])
        for codigo, etiqueta in RESULTADOS.items()
    ]

    sin_resultado = total - len(resultados_por_id)
    if sin_resultado:
        cantidades.append(("Sin resultado reconocido", sin_resultado))

    filas = [
        {
            "Resultado": etiqueta,
            "Cantidad": cantidad,
            "Porcentaje": f"{cantidad / total:.2%}" if total else "—",
        }
        for etiqueta, cantidad in cantidades
    ]
    return total, filas


def leer_fecha(actividades, actividad_id, campo):
    registro = actividades.get(actividad_id, {})
    valor = registro.get(campo)
    if not valor:
        raise ValueError(f"Falta {campo} para la actividad {actividad_id}.")

    # Flowable puede devolver zonas horarias como Z, -0300 o -03:00.
    valor = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", valor)
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def segundos_entre(inicio, fin):
    segundos = (fin - inicio).total_seconds()
    if segundos < 0:
        raise ValueError("El fin de una rama es anterior a su inicio.")
    return segundos


def medir_ramas(actividades):
    por_id = {
        actividad["activityId"]: actividad
        for actividad in actividades
    }

    recursos = [
        actividad_id
        for actividad_id in ACTIVIDADES_RECURSOS
        if actividad_id in por_id
    ]
    if not recursos:
        raise ValueError("Faltan las actividades de recursos en el historial.")

    inscripciones = segundos_entre(
        leer_fecha(por_id, "Nomina", "startTime"),
        leer_fecha(por_id, "Lista", "endTime"),
    )
    materiales = segundos_entre(
        leer_fecha(por_id, "Material", "startTime"),
        leer_fecha(por_id, "Material", "endTime"),
    )
    fin_recursos = max(
        leer_fecha(por_id, actividad_id, "endTime")
        for actividad_id in recursos
    )
    duracion_recursos = segundos_entre(
        leer_fecha(por_id, "Activity_12i2hpf", "startTime"),
        fin_recursos,
    )

    return inscripciones, materiales, duracion_recursos


def calcular_preparacion(sesion, definiciones):
    """4.3.2. Mide las preparaciones que llegaron a su fin normal."""
    muestras = []
    incompletas = []

    for definicion in definiciones:
        cierres = listar(
            sesion,
            HISTORIAL_ACTIVIDADES,
            processDefinitionId=definicion,
            activityId="SubFin",
            finished="true",
        )
        instancias_preparadas = {
            cierre["processInstanceId"] for cierre in cierres
        }

        for instancia_id in sorted(instancias_preparadas):
            actividades = list(
                listar(
                    sesion,
                    HISTORIAL_ACTIVIDADES,
                    processInstanceId=instancia_id,
                )
            )
            try:
                muestras.append(medir_ramas(actividades))
            except (TypeError, ValueError) as error:
                incompletas.append(f"{instancia_id} — {error}")

    filas = [
        {
            "Rama": rama,
            "Promedio (segundos)": (
                round(mean(muestra[indice] for muestra in muestras), 3)
                if muestras
                else None
            ),
        }
        for indice, rama in enumerate(RAMAS)
    ]
    return len(muestras), filas, incompletas


def calcular_distribucion(sesion, definiciones):
    """4.3.3. Cuenta las tareas completadas por integrante."""
    grupos_por_usuario = defaultdict(list)

    for grupo_id, etiqueta in GRUPOS.items():
        for usuario in listar(sesion, "identity/users", memberOfGroup=grupo_id):
            grupos_por_usuario[usuario["id"]].append(etiqueta)

    conteos = Counter()

    for definicion in definiciones:
        tareas = listar(
            sesion,
            HISTORIAL_TAREAS,
            processDefinitionId=definicion,
            finished="true",
        )
        for tarea in tareas:
            responsable = tarea.get("assignee")
            # Las tareas interrumpidas también pueden tener fecha de fin.
            if (
                responsable in grupos_por_usuario
                and tarea.get("endTime")
                and tarea["deleteReason"] is None
            ):
                conteos[responsable] += 1

    filas = [
        {
            "Grupo": ", ".join(grupos),
            "Usuario de Flowable": usuario,
            "Tareas completadas": conteos[usuario],
        }
        for usuario, grupos in grupos_por_usuario.items()
    ]
    return sorted(filas, key=lambda fila: (fila["Grupo"], fila["Usuario de Flowable"]))


def mostrar_analisis(sesion):
    instancias = list(
        listar(sesion, HISTORIAL_PROCESOS, processDefinitionKey=PROCESS_KEY)
    )
    definiciones = sorted({
        instancia["processDefinitionId"] for instancia in instancias
    })

    total, resultados = calcular_resultados(sesion, instancias)
    cantidad, promedios, incompletas = calcular_preparacion(sesion, definiciones)
    distribucion = calcular_distribucion(sesion, definiciones)

    st.subheader("Resultados de las solicitudes")
    st.metric("Instancias terminadas", total)
    st.dataframe(resultados, hide_index=True)

    st.subheader("Preparación paralela")
    st.metric("Preparaciones medidas", cantidad)
    if cantidad:
        st.dataframe(promedios, hide_index=True)
    else:
        st.info("Todavía no hay preparaciones con historial suficiente para medir.")

    if incompletas:
        with st.expander(f"Preparaciones con historial incompleto ({len(incompletas)})"):
            for detalle in incompletas:
                st.text(detalle)

    st.subheader("Distribución de tareas")
    if distribucion:
        st.dataframe(distribucion, hide_index=True)
    else:
        st.info("No se encontraron integrantes en los grupos de Flowable configurados.")


def pantalla_analisis(mostrar_titulo=True):
    if mostrar_titulo:
        st.title("Análisis de las ejecuciones")

    with st.form("consulta_historial"):
        usuario = st.text_input("Usuario de Flowable", value="admin").strip()
        clave = st.text_input("Contraseña de Flowable", type="password")
        consultar = st.form_submit_button("Consultar historial")

    if not consultar:
        return

    if not usuario or not clave:
        st.warning("Ingresá el usuario y la contraseña de Flowable.")
        return

    try:
        with st.spinner("Consultando el historial de Flowable…"):
            with requests.Session() as sesion:
                sesion.auth = (usuario, clave)
                mostrar_analisis(sesion)
    except requests.HTTPError as error:
        estado = error.response.status_code
        if estado in (401, 403):
            st.error("Revisá las credenciales y los permisos de acceso al historial.")
        else:
            st.error(f"Flowable devolvió un error HTTP {estado}.")
    except requests.RequestException:
        st.error(f"No se pudo conectar con Flowable en {FLOWABLE_URL}.")
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        st.error(f"No se pudo interpretar el historial de Flowable. Detalle: {error}")


if __name__ == "__main__":
    st.set_page_config(page_title="Análisis de las ejecuciones")
    pantalla_analisis()
