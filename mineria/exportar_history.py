import csv
import os
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from getpass import getpass
from pathlib import Path

import requests


# Configuración
BASE_URL = "http://localhost:8080/flowable-ui/process-api"
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

# BPMN local: solo se usa si es idéntico al publicado en Flowable.
BPMN_LOCAL = (
    Path(__file__).resolve().parent.parent
    / "models" / "Institucion_de_capacitacion.bpmn20.xml"
)

# ID del elemento <process id="..."> del BPMN.
PROCESS_KEY = "Process_Curso"

# IDs BPMN de las actividades y eventos de la etapa de negociación
# (etapa previa a la preparación del curso).
ACTIVIDADES = {
    "Activity_1xw400l",  # Evaluar Viabilidad
    "Activity_0iibzwu",  # Notificar Decisión (solicitud no viable)
    "Propuesta",         # Registrar y Elaborar propuesta
    "Enviar",            # Enviar propuesta
    "Modificar",         # Modificaciones (mensaje de la empresa)
    "Revisar",           # Revisar propuesta
    "Plazo",             # 5 días (temporizador)
    "Recordatorio",      # Enviar recordatorio
    "Rechazar",          # Rechazo (mensaje de la empresa)
    "Archivar",          # Archivar solicitud
    "Aceptar",           # Aceptación (mensaje de la empresa)
    "Activity_1eg7zcl",  # Habilitar acceso de la empresa
}

ARCHIVO_SALIDA = "eventos.csv"


def consultar_todos(session, recurso, filtros):
    """Recupera todas las páginas de una consulta REST."""
    inicio = 0

    while True:
        respuesta = session.get(
            f"{BASE_URL}/{recurso}",
            params={
                **filtros,
                "start": inicio,
                "size": 100,
            },
            timeout=30,
        )
        respuesta.raise_for_status()
        pagina = respuesta.json()
        registros = pagina["data"]

        if not registros:
            break

        yield from registros
        inicio += len(registros)

        if inicio >= pagina["total"]:
            break


def fecha_iso(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def normalizar_xml(contenido):
    """Quita saltos de línea y espacios para comparar dos BPMN."""
    return "".join(contenido.decode("utf-8").split())


def bpmn_local_si_coincide(session):
    """
    Devuelve el BPMN local (models/) solo si es idéntico al último
    modelo de PROCESS_KEY publicado en Flowable; si no, None.
    """
    respuesta = session.get(
        f"{BASE_URL}/repository/process-definitions",
        params={"key": PROCESS_KEY, "latest": "true"},
        timeout=30,
    )
    respuesta.raise_for_status()
    publicados = respuesta.json()["data"]
    if not publicados:
        return None

    publicado = session.get(
        f"{BASE_URL}/repository/process-definitions/"
        f"{publicados[0]['id']}/resourcedata",
        timeout=30,
    )
    publicado.raise_for_status()
    local = BPMN_LOCAL.read_bytes()

    if normalizar_xml(local) != normalizar_xml(publicado.content):
        return None
    return local


def modelo_publicado(session, definicion_id, cache):
    """
    Lee de Flowable el BPMN publicado de esa versión del proceso y
    devuelve {id_flujo: id_origen}.

    Si esa versión ya no está publicada, se usa el BPMN local solo
    cuando es idéntico al último modelo publicado en Flowable. En
    cualquier otro caso devuelve None y la instancia se excluye.
    """
    if definicion_id not in cache:
        respuesta = session.get(
            f"{BASE_URL}/repository/process-definitions/"
            f"{definicion_id}/resourcedata",
            timeout=30,
        )
        if respuesta.status_code == 404:
            if "local" not in cache:
                cache["local"] = bpmn_local_si_coincide(session)
            contenido = cache["local"]
        else:
            respuesta.raise_for_status()
            contenido = respuesta.content

        if contenido is None:
            cache[definicion_id] = None
        else:
            raiz = ET.fromstring(contenido)
            cache[definicion_id] = {
                flujo.get("id"): flujo.get("sourceRef")
                for flujo in raiz.iter(f"{{{BPMN_NS}}}sequenceFlow")
            }
    return cache[definicion_id]


def actividades_ocurridas(actividades, origen_de_flujo):
    """
    Devuelve los IDs de las actividades históricas que realmente
    ocurrieron.

    Flowable registra con endTime elementos que no ocurrieron: detrás
    del gateway basado en eventos ("Esperar respuesta") cierra todos
    los eventos que estaban esperando aunque solo uno se haya
    disparado, y lo mismo pasa con tareas interrumpidas. Por eso una
    actividad se considera ocurrida únicamente si se tomó un flujo de
    secuencia que sale de ella. Si un mismo elemento se ejecutó varias
    veces (p. ej. varias modificaciones), cada flujo tomado se asocia
    a la ejecución que terminó más cerca antes de ese flujo.
    """
    finalizadas = [
        a for a in actividades
        if a["activityType"] != "sequenceFlow" and a.get("endTime")
    ]
    flujos = sorted(
        (a for a in actividades if a["activityType"] == "sequenceFlow"),
        key=lambda a: fecha_iso(a["startTime"]),
    )

    ocurridas = set()
    for flujo in flujos:
        origen = origen_de_flujo.get(flujo["activityId"])
        candidatas = [
            a for a in finalizadas
            if a["activityId"] == origen
            and a["id"] not in ocurridas
            and fecha_iso(a["endTime"]) <= fecha_iso(flujo["startTime"])
        ]
        if candidatas:
            elegida = max(candidatas, key=lambda a: fecha_iso(a["endTime"]))
            ocurridas.add(elegida["id"])
    return ocurridas


def main():
    # ejecutar_mineria.sh pasa las credenciales por variables de entorno, si no están, se piden por consola.
    usuario = os.environ.get("FLOWABLE_USER") or input("Usuario de Flowable: ")
    clave = os.environ.get("FLOWABLE_PASS") or getpass("Contraseña: ")

    eventos = []
    modelos = {}
    excluidas = Counter()
    descartados = Counter()

    with requests.Session() as session:
        session.auth = (usuario, clave)

        # Se incluyen también las instancias en curso: un curso que está
        # en preparación o en dictado ya completó su negociación.
        # No se filtra con "processDefinitionKey" en la consulta porque
        # el historial de Flowable lo deja vacío; se filtra por el
        # prefijo del processDefinitionId ("Process_Curso:<versión>:...").
        instancias = consultar_todos(
            session,
            "history/historic-process-instances",
            {},
        )

        for instancia in instancias:
            definicion = instancia["processDefinitionId"]
            if not definicion.startswith(f"{PROCESS_KEY}:"):
                continue

            # Excluir instancias eliminadas o canceladas
            # administrativamente.
            if instancia.get("deleteReason"):
                excluidas["eliminadas por un administrador"] += 1
                continue

            origen_de_flujo = modelo_publicado(session, definicion, modelos)
            if origen_de_flujo is None:
                excluidas[
                    f"versión {definicion.split(':')[1]} no publicada "
                    "(y el BPMN local difiere del publicado)"
                ] += 1
                continue

            actividades = list(consultar_todos(
                session,
                "history/historic-activity-instances",
                {"processInstanceId": instancia["id"]},
            ))
            ocurridas = actividades_ocurridas(actividades, origen_de_flujo)

            for actividad in actividades:
                if actividad["activityId"] not in ACTIVIDADES:
                    continue

                # No exportar elementos pendientes ni elementos que
                # Flowable cerró sin que hayan ocurrido.
                if not actividad.get("endTime"):
                    continue
                if actividad["id"] not in ocurridas:
                    descartados[
                        actividad.get("activityName")
                        or actividad["activityId"]
                    ] += 1
                    continue

                eventos.append({
                    "instancia": instancia["id"],
                    "definicion": definicion,
                    "evento_id": actividad["id"],
                    "actividad_id": actividad["activityId"],
                    "actividad": (
                        actividad.get("activityName")
                        or actividad["activityId"]
                    ),
                    "tipo": actividad["activityType"],
                    "inicio": actividad["startTime"],
                    "fecha_hora": actividad["endTime"],
                    "recurso": actividad.get("assignee") or "",
                })

    # Ordenar por instancia y fecha de finalización.
    # El ID da un orden estable si coinciden las marcas temporales.
    eventos.sort(
        key=lambda evento: (
            evento["instancia"],
            fecha_iso(evento["fecha_hora"]),
            fecha_iso(evento["inicio"]),
            evento["evento_id"],
        )
    )

    columnas = [
        "instancia", "definicion", "evento_id",
        "actividad_id", "actividad", "tipo",
        "inicio", "fecha_hora", "recurso",
    ]

    with open(
        ARCHIVO_SALIDA, "w", newline="", encoding="utf-8"
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(eventos)

    cantidad_instancias = len({
        evento["instancia"] for evento in eventos
    })

    print(
        f"Generado {ARCHIVO_SALIDA}: "
        f"{len(eventos)} eventos de {cantidad_instancias} instancias."
    )

    if excluidas:
        print("\nInstancias excluidas:")
        for motivo, cantidad in excluidas.most_common():
            print(f"- {cantidad} {motivo}")

    if descartados:
        print("\nEventos descartados por no haber ocurrido:")
        for nombre, cantidad in descartados.most_common():
            print(f"- {nombre}: {cantidad}")


if __name__ == "__main__":
    main()
