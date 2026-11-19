import datetime
import re

import requests
import streamlit as st

from navegacion import cerrar_sesion, ir_a
from servicios import (FLOWABLE_URL, GRUPO_DOCENTES, VAR_RESUMEN_INFORME,
                       descargar_pdf_informe, guardar_informe_bd, guardar_pdf_informe,
                       obtener_docentes, obtener_solicitud, obtener_tareas_personal)

# pantalla cuando un usuario inicia sesion
def pantalla_panel_personal():
    usuario = st.session_state.usuario
    st.title("🧑‍💼 Panel del personal")
    st.caption(f"{usuario['nombre']} · usuario {usuario['usuario']}")
    col1, col2 = st.columns(2)
    with col1:
        st.button("Cerrar sesion", on_click=cerrar_sesion, use_container_width=True)
    with col2:
        st.button("🔄 Actualizar", use_container_width=True)  # para actualizar las consultas
    st.divider()

    # resultado de la ultima accion (reclamar / completar)
    aviso = st.session_state.pop("aviso_tarea", None)
    if aviso:
        (st.success if aviso[0] == "ok" else st.error)(aviso[1])

    try:
        asignadas = obtener_tareas_personal(usuario, "assignee")
        # candidateUser: tareas sin asignar donde el usuario es candidato, directo o por su grupo
        disponibles = obtener_tareas_personal(usuario, "candidateUser")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            st.error("Flowable rechazo las credenciales del usuario. Cierre sesion y vuelva a ingresar.")
        else:
            st.error(f"No se pudieron consultar las tareas: {e}")
        return
    except requests.RequestException as e:
        st.error(f"No se pudo conectar con Flowable: {e}")
        return

    st.subheader(f"Mis tareas asignadas ({len(asignadas)})")
    if asignadas:
        for tarea in asignadas:
            mostrar_tarea(tarea, "completar")
    else:
        st.caption("No tiene tareas asignadas.")

    st.subheader(f"Disponibles para mi grupo ({len(disponibles)})")
    if disponibles:
        st.caption("Tareas sin asignar que puede reclamar cualquier integrante del grupo.")
        for tarea in disponibles:
            mostrar_tarea(tarea, "reclamar")
    else:
        st.caption("No hay tareas disponibles para su grupo.")


def mostrar_tarea(tarea, accion):
    """Muestra una tarea para que sea completada o reclamada"""
    variables = {v["name"]: v.get("value") for v in tarea.get("variables", [])}
    # algunos nombres del modelo tienen saltos de linea
    nombre = " ".join((tarea.get("name") or "Tarea sin nombre").split())
    task_key = tarea.get("taskDefinitionKey")

    with st.container(border=True):
        st.markdown(f"**{nombre}**")
        curso = variables.get("tematica") or "Curso sin nombre"
        empresa = variables.get("nombreEmpresa") or "Empresa no informada"
        st.write(f"Curso: {curso} · Empresa: {empresa}")
        creada = (tarea.get("createTime") or "")[:16].replace("T", " ")
        st.caption(
            f"Curso N.º {variables.get('idCurso', '-')} · Creada: {creada} UTC · "
            f"Instancia {tarea.get('processInstanceId')}"
        )

        # si la tarea tiene un formulario propio se muestra ese
        formulario = FORMULARIOS_POR_TAREA.get(task_key)
        if accion == "completar" and formulario:
            formulario(tarea, nombre, variables)
            return

        # el resto de las tareas solo tienen un boton para completar o reclamar
        if accion == "completar" and task_key == "Dictar":
            texto_boton = "🎓 Registrar finalizacion del dictado"
        elif accion == "completar":
            texto_boton = "✅ Completar"
        else:
            texto_boton = "✋ Reclamar"

        st.button(
            texto_boton,
            key=f"{accion}_{tarea['id']}",
            on_click=accion_tarea,
            args=(tarea["id"], nombre, accion),
            type="primary" if accion == "completar" else "secondary",
        )

def accion_tarea(id_tarea, nombre, accion, variables=None):
    """Reclama o completa una tarea en flowable con las credenciales del usuario. Se en los botones"""
    usuario = st.session_state.usuario

    # si se completa una tarea y ademas tiene variables, se pasan en el cuerpo, por ejemplo los formularios de la propuesta(generar o revisar)
    if accion == "reclamar":
        cuerpo = {"action": "claim", "assignee": usuario["usuario"]}
    else:
        cuerpo = {"action": "complete"}
        if variables:
            cuerpo["variables"] = variables

    hecho = "reclamada: ahora esta en sus tareas asignadas" if accion == "reclamar" else "completada"
    try:
        # antes de actuar se vuelve a leer la tarea: otro usuario pudo reclamarla o completarla
        actual = requests.get(f"{FLOWABLE_URL}/runtime/tasks/{id_tarea}",
                              auth=(usuario["usuario"], usuario["clave"]), timeout=10)
        if actual.status_code == 404:
            st.session_state.aviso_tarea = ("error", f"La tarea '{nombre}' ya no esta pendiente.")
            return
        actual.raise_for_status()
        asignada_a = actual.json().get("assignee")
        if accion == "reclamar" and asignada_a:
            st.session_state.aviso_tarea = ("error", f"La tarea '{nombre}' ya fue reclamada por {asignada_a}.")
            return
        if accion == "completar" and asignada_a != usuario["usuario"]:
            st.session_state.aviso_tarea = ("error", f"La tarea '{nombre}' no esta asignada a usted.")
            return

        respuesta = requests.post(f"{FLOWABLE_URL}/runtime/tasks/{id_tarea}", json=cuerpo,
                                  auth=(usuario["usuario"], usuario["clave"]), timeout=15)
    except requests.RequestException as e:
        st.session_state.aviso_tarea = ("error", f"No se pudo conectar con Flowable: {e}")
        return

    if respuesta.status_code in (200, 201, 204):
        st.session_state.aviso_tarea = ("ok", f"Tarea '{nombre}' {hecho}.")
    elif respuesta.status_code == 409:
        st.session_state.aviso_tarea = ("error", f"La tarea '{nombre}' ya fue reclamada por otro usuario.")
    elif respuesta.status_code == 404:
        st.session_state.aviso_tarea = ("error", f"La tarea '{nombre}' ya no esta pendiente.")
    else:
        try:
            detalle = respuesta.json().get("exception") or respuesta.json().get("message")
        except ValueError:
            detalle = respuesta.text
        st.session_state.aviso_tarea = ("error", f"No se pudo {accion} la tarea '{nombre}': {detalle}")

# parte de la administracion
def mostrar_solicitud(tarea, variables):
    """Muestra en un desplegable los datos del formulario de solicitud de la empresa para el jefeAdministrativo"""
    with st.expander("🏢 Solicitud de la empresa", expanded=True):
        try:
            datos = obtener_solicitud(variables.get("idCurso"), tarea.get("processInstanceId"))
        except Exception as e:
            st.warning(f"No se pudieron cargar los datos de la solicitud: {e}")
            return

        if not datos:
            st.info("No se encontro la solicitud de la empresa en la base de datos.")
            return

        def valor(campo, defecto="No informado"):
            dato = datos.get(campo)
            return dato if dato not in (None, "") else defecto

        tematica = variables.get("tematica") or valor("nombre")

        col_empresa, col_curso = st.columns(2)
        with col_empresa:
            st.markdown("**Datos de la empresa**")
            st.write(f"**Razón social:** {valor('nombre_empresa')}")
            st.write(f"**CUIT:** {valor('cuit')}")
            st.write(f"**Persona de contacto:** {valor('persona_contacto')}")
            st.write(f"**Email de contacto:** {valor('email_contacto')}")
        with col_curso:
            st.markdown("**Datos del curso solicitado**")
            st.write(f"**Temática:** {tematica}")
            st.write(f"**Participantes aprox.:** {valor('cantidad_participantes')}")
            st.write(f"**Fechas preferidas:** {valor('fechas_preferidas')}")

        st.markdown("**Descripción de la necesidad**")
        st.text(valor("descripcion", "Sin descripción"))

# formulario que se usa tanto en Registrar y Revisar propuesta
def form_propuesta(tarea, nombre, variables):
    es_revision = tarea.get("taskDefinitionKey") == "Revisar"

    mostrar_solicitud(tarea, variables)

    if es_revision:
        obs = variables.get("observaciones") or "Sin observaciones detalladas."
        st.warning(f"📝 **Observaciones de la empresa:** {obs}")

    nombre_fijo = variables.get("nombreCurso") or variables.get("tematica") or ""

    with st.form(key=f"form_propuesta_{tarea['id']}"):
        # en revision mostramos el nombre como lectura para no cambiar el curso solicitado
        if es_revision:
            st.text_input("Curso", value=nombre_fijo, disabled=True)
            nombre_curso = nombre_fijo
        else:
            nombre_curso = st.text_input("Nombre del curso *", value=nombre_fijo)

        programa = st.text_area(
            "Programa del curso *",
            value=variables.get("programa") or ""
        )

        col1, col2 = st.columns(2)
        with col1:
            presupuesto = st.number_input(
                "Presupuesto ($) *",
                min_value=0.0,
                step=1000.0,
                value=float(variables.get("presupuesto") or 0.0)
            )
            fecha1 = st.date_input(
                "Fecha posible 1 *",
                value=parsear_fecha_ui(variables.get("fechaposible1"), datetime.date.today() + datetime.timedelta(days=7))
            )

        with col2:
            usar_f2 = st.checkbox("Incluir fecha posible 2", value=bool(variables.get("fechaposible2")))
            fecha2 = st.date_input(
                "Fecha posible 2",
                value=parsear_fecha_ui(variables.get("fechaposible2"), datetime.date.today() + datetime.timedelta(days=14))
            )

        otras_fechas = st.text_input(
            "Otras fechas (opcional)",
            value=variables.get("otrasfechasopcional") or ""
        )

        texto_btn = "📤 Enviar propuesta revisada" if es_revision else "📤 Generar PDF y enviar propuesta"
        enviado = st.form_submit_button(texto_btn, type="primary", use_container_width=True)

    if enviado:
        if not nombre_curso.strip() or not programa.strip():
            st.error("El nombre del curso y el programa son obligatorios.")
            return

        payload_vars = [
            {"name": "nombreCurso", "value": nombre_curso.strip()},
            {"name": "programa", "value": programa.strip()},
            {"name": "presupuesto", "value": float(presupuesto)},
            {"name": "fechaposible1", "value": fecha1.isoformat()},
            {"name": "fechaposible2", "value": fecha2.isoformat() if usar_f2 else ""},
            {"name": "otrasfechasopcional", "value": otras_fechas.strip()},
        ]
        accion_tarea(tarea["id"], nombre, "completar", payload_vars)
        st.rerun()

# funcion aux para convertir un texto en una lista de participantes (lista definitiva)
def separar_participantes(texto, separadores=r"\n"):
    participantes = []
    vistos = set()
    for parte in re.split(f"[{separadores}]+", str(texto or "")):
        nombre = " ".join(parte.split())
        if nombre and nombre.casefold() not in vistos:
            vistos.add(nombre.casefold())
            participantes.append(nombre)
    return participantes

def form_lista_definitiva(tarea, nombre, variables):
    """
    Se parte de la nomina que envio la empresa (variable 'nominaParticipantes'), el administrativo
    la corrige si hace falta y al completar la lista queda guardada como variables del proceso:
    'listaDefinitiva' (un participante por renglon) y 'cantidadInscriptos'.
    """
    nomina = variables.get("nominaParticipantes")
    # la nomina de la empresa llega separada por comas (o por renglones)
    recibidos = separar_participantes(nomina, separadores=r",;\n")

    if recibidos:
        st.info(f"📋 Nomina enviada por la empresa: {len(recibidos)} participante(s).")
    else:
        st.warning("La instancia no tiene una nomina cargada. Ingrese los participantes manualmente.")

    with st.form(key=f"form_lista_{tarea['id']}"):
        texto = st.text_area(
            "Lista definitiva de participantes * (uno por renglon)",
            value=variables.get("listaDefinitiva") or "\n".join(recibidos),
            height=220,
        )
        enviado = st.form_submit_button("📋 Confirmar lista definitiva y completar", type="primary",
                                        use_container_width=True)

    if enviado:
        lista = separar_participantes(texto)
        if not lista:
            st.error("La lista definitiva debe tener al menos un participante.")
            return

        accion_tarea(tarea["id"], nombre, "completar", [
            {"name": "listaDefinitiva", "value": "\n".join(lista)},
            {"name": "cantidadInscriptos", "value": len(lista)},
        ])
        st.rerun()

# recursos que se pueden pedir en 'Evaluar recursos': (variable del proceso, etiqueta, que hace el motor)
# las variables son las condiciones de la compuerta inclusiva 'Recursos necesarios' del modelo
RECURSOS_CURSO = [
    ("requiereAula", "🏫 Aula fisica", "La reserva del aula es automatica."),
    ("requierePlataforma", "💻 Aula virtual", "Se crea la tarea 'Solicitar Aula Virtual'."),
    ("requiereEquipamiento", "🎛️ Equipamiento especial", "Se crea la tarea 'Contratar equipamiento'."),
]

def boton_evaluar_recursos(tarea, nombre, variables):
    """En el panel, evaluar recursos solo muestra un boton: el formulario esta en una pagina propia"""
    st.button("🧰 Seleccionar recursos", key=f"recursos_{tarea['id']}",
              on_click=abrir_evaluar_recursos, args=(tarea, nombre, variables), type="primary")

def abrir_evaluar_recursos(tarea, nombre, variables):
    """Callback del panel: guarda la tarea elegida y abre la pagina de seleccion de recursos"""
    st.session_state.tarea_recursos = {
        "id": tarea["id"],
        "nombre": nombre,
        "curso": variables.get("tematica") or "Curso sin nombre",
        "empresa": variables.get("nombreEmpresa") or "Empresa no informada",
        "id_curso": variables.get("idCurso", "-"),
    }
    st.session_state.pagina = "panel_recursos"

def pantalla_evaluar_recursos():
    """
    Pagina para elegir aula fisica, aula virtual y/o equipamiento especial (al menos uno).
    Al completar se mandan las tres variables booleanas y el motor activa solo las ramas elegidas.
    """
    datos = st.session_state.get("tarea_recursos")
    if not datos:
        st.session_state.pagina = "panel_personal"
        st.rerun()

    st.button("⬅ Volver al panel", on_click=ir_a, args=("panel_personal",))
    st.title("🧰 Evaluar recursos")
    st.write(f"Curso: {datos['curso']} · Empresa: {datos['empresa']}")
    st.caption(f"Curso N.º {datos['id_curso']}")

    with st.form(key=f"form_recursos_{datos['id']}"):
        st.markdown("**Recursos necesarios para el curso *** (seleccione al menos uno)")
        elegidos = {}
        for variable, etiqueta, efecto in RECURSOS_CURSO:
            elegidos[variable] = st.checkbox(etiqueta, help=efecto)
        enviado = st.form_submit_button("🧰 Confirmar recursos y completar", type="primary",
                                        use_container_width=True)

    if enviado:
        if not any(elegidos.values()):
            st.error("Debe seleccionar al menos un recurso.")
            return

        # se mandan las tres, tambien las que quedan en false: la compuerta evalua todas las condiciones
        accion_tarea(datos["id"], datos["nombre"], "completar",
                     [{"name": variable, "value": bool(valor)} for variable, valor in elegidos.items()])
        # el resultado (ok o error) se muestra en el panel
        st.session_state.pop("tarea_recursos", None)
        st.session_state.pagina = "panel_personal"
        st.rerun()

def form_definir_docente(tarea, nombre, variables):
    """
    El jefe elige un integrante del equipo (puede ser el mismo) y completa la tarea.
    (variables no se usa: esta para que todos los formularios reciban los mismos parametros)
    El elegido se guarda en la variable 'docenteAsignadoCurso'; la tarea 'Desarrollar curso'
    la usa como responsable (${docenteAsignadoCurso}) cuando se crea.
    """
    usuario = st.session_state.usuario
    try:
        docentes = obtener_docentes()
    except requests.RequestException as e:
        st.error(f"No se pudo obtener el equipo docente: {e}")
        return

    if not docentes:
        st.warning(f"El grupo '{GRUPO_DOCENTES}' no tiene integrantes en Flowable.")
        return

    nombres = {}
    for d in docentes:
        completo = " ".join(p for p in (d.get("firstName"), d.get("lastName")) if p) or d["id"]
        nombres[d["id"]] = f"{completo} ({d['id']})" + (" — usted" if d["id"] == usuario["usuario"] else "")

    with st.form(key=f"form_docente_{tarea['id']}"):
        elegido = st.selectbox(
            "Docente que desarrollara el curso *",
            options=list(nombres.keys()),
            format_func=lambda id_docente: nombres[id_docente],
        )
        enviado = st.form_submit_button("👩‍🏫 Asignar docente y completar", type="primary",
                                        use_container_width=True)

    if enviado:
        accion_tarea(tarea["id"], nombre, "completar",
                     [{"name": "docenteAsignadoCurso", "value": elegido}])
        st.rerun()


def form_informe(tarea, nombre, variables):
    """
    El jefe escribe el resumen de resultados y adjunta el informe en PDF. El resumen se guarda en la
    base (curso.informe_resultados) y en la variable 'informeResultados'; el PDF en 'pdfInforme'.
    """
    with st.form(key=f"form_informe_{tarea['id']}"):
        resumen = st.text_area("Resumen de resultados *", value=variables.get(VAR_RESUMEN_INFORME) or "",
                               height=160)
        archivo = st.file_uploader("Informe en PDF *", type=["pdf"])
        enviado = st.form_submit_button("📄 Guardar informe y completar", type="primary",
                                        use_container_width=True)

    if enviado:
        if not resumen.strip() or archivo is None:
            st.error("El resumen de resultados y el informe en PDF son obligatorios.")
            return
        contenido = archivo.getvalue()
        if not contenido.startswith(b"%PDF"):
            st.error("El archivo adjunto no es un PDF valido.")
            return

        id_instancia = tarea.get("processInstanceId")
        try:
            guardar_informe_bd(id_instancia, resumen.strip())
            guardar_pdf_informe(id_instancia, contenido, st.session_state.usuario)
        except Exception as e:
            st.error(f"No se pudo guardar el informe: {e}")
            return

        accion_tarea(tarea["id"], nombre, "completar",
                     [{"name": VAR_RESUMEN_INFORME, "value": resumen.strip()}])
        st.rerun()

def panel_enviar_informe(tarea, nombre, variables):
    """
    Consultar el informe de resultados (resumen y PDF) y completar
    'Enviar informe a empresa y archivar expediente'.
    """
    id_instancia = tarea.get("processInstanceId")
    resumen = variables.get(VAR_RESUMEN_INFORME)
    try:
        pdf = descargar_pdf_informe(id_instancia, st.session_state.usuario)
    except requests.RequestException as e:
        pdf = None
        st.error(f"No se pudo consultar el PDF del informe: {e}")

    st.markdown("**Informe de resultados**")
    if resumen:
        st.text(resumen)
    if pdf:
        st.download_button("📥 Descargar informe (PDF)", data=pdf,
                           file_name=f"Informe_curso_{variables.get('idCurso', id_instancia)}.pdf",
                           mime="application/pdf", key=f"pdf_informe_{tarea['id']}")
    if not resumen and not pdf:
        st.warning("Esta instancia no tiene un informe cargado desde el sitio. "
                   "Si se elaboro desde Flowable, consultelo alli antes de enviarlo.")

    st.button("📨 Enviar informe a la empresa y archivar expediente", key=f"completar_{tarea['id']}",
              on_click=accion_tarea, args=(tarea["id"], nombre, "completar"), type="primary")

# id de la tarea en el modelo BPMN -> funcion que dibuja su formulario.
# Todas reciben (tarea, nombre, variables). Las tareas que no estan aca
# solo muestran el boton de completar.
FORMULARIOS_POR_TAREA = {
    "Propuesta": form_propuesta,                    # Registrar y Elaborar propuesta
    "Revisar": form_propuesta,                      # Revisar propuesta
    "Lista": form_lista_definitiva,                 # Confeccionar lista definitiva
    "Activity_12i2hpf": boton_evaluar_recursos,     # Evaluar Recursos
    "Activity_1018bdz": form_definir_docente,       # Definir Docente que desarrolla el curso
    "Informe": form_informe,                        # Elaborar informe de resultados
    "EnviarInforme": panel_enviar_informe,          # Enviar informe a empresa y Archivar expediente
}

# funcion aux
def parsear_fecha_ui(valor, defecto):
    """Para que no haya error de tipos, ya que flowable da la fecha en formato texto, convierte texto a date"""
    if not valor:
        return defecto
    try:
        return datetime.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return defecto