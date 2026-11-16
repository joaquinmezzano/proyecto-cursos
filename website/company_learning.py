import streamlit as st
import psycopg2
import requests
import hashlib
import hmac
import re
import datetime

# configuracion flowable y bdd de institucion
FLOWABLE_URL = "http://localhost:8080/flowable-ui/process-api"
FLOWABLE_USER = "admin"
FLOWABLE_PASS = "test"
PROCESS_KEY = "Process_Curso"

DB_HOST = "localhost"
DB_PORT = "5434"
DB_NAME = "institucion"
DB_USER = "flowable"
DB_PASS = "flow10"

def db_conexion():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

# formulario a llenar de un cliente de la empresa
st.set_page_config(page_title="Institucion de Capacitacion", page_icon="🏢", layout="centered")

# esto es para la navegacion. se guarda la pantalla y quien esta logueado
if "pagina" not in st.session_state:
    st.session_state.pagina = "inicio"
if "usuario" not in st.session_state:
    st.session_state.usuario = None   # dict con los datos del usuario logueado

def ir_a(pagina):
    st.session_state.pagina = pagina

def cerrar_sesion():
    st.session_state.usuario = None
    st.session_state.pagina = "inicio"

def boton_volver():
    st.button("⬅ Volver al inicio", on_click=ir_a, args=("inicio",))

# pantalla principal
def pantalla_inicio():
    st.title("🏢 Institucion de Capacitacion")
    st.markdown("Bienvenido. ¿Que desea hacer?")
    st.write("")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("📝 Solicitar un curso")
            st.caption("Complete el formulario para pedir una capacitacion para su empresa. No necesita cuenta.")
            st.button("Completar formulario", on_click=ir_a, args=("formulario",),
                      use_container_width=True, type="primary")
    with col2:
        with st.container(border=True):
            st.subheader("🔐 Iniciar sesion")
            st.caption("Si su empresa ya acepto una propuesta, ingrese para ver el estado de sus cursos.")
            st.button("Ingresar", on_click=ir_a, args=("login",), use_container_width=True)


# formulario de solicitud
def pantalla_formulario():
    boton_volver()

    st.title("🏢 Solicitud de capacitacion")
    st.markdown("Complete este formulario para solicitar un curso para su empresa.")

    with st.form("form_solicitud"):
        st.subheader("1. Datos de la empresa")
        col1, col2 = st.columns(2)
        with col1:
            cuit = st.text_input("CUIT de la empresa * (Ej: 30-12345678-9)")
            nombre_empresa = st.text_input("Nombre / Razón Social *")
        with col2:
            persona_contacto = st.text_input("Persona de Contacto *")
            email_contacto = st.text_input("Email de Contacto *")

        st.subheader("2. Datos del curso")
        col3, col4 = st.columns(2)
        with col3:
            tematica = st.text_input("Tematica o nombre del curso *")
            cantidad_participantes = st.number_input("Cantidad de participantes aprox *", min_value=1, value=10)
        with col4:
            fechas_preferidas = st.text_input("Fechas preferidas *")

        descripcion = st.text_area("Descripción detallada de la necesidad *")

        submit_btn = st.form_submit_button("Enviar solicitud", use_container_width=True)

    if submit_btn:
        # caso negativo, por si falta algo de data
        if not cuit or not nombre_empresa or not tematica or not descripcion:
            st.error("Por favor, complete todos los campos obligatorios (*).")
        else:
            conn = db_conexion()
            if conn:
                try:
                    cursor = conn.cursor()

                    # se busca la empresa si esta en la bdd(podria estar por otros cursos antes), sino se crea
                    cursor.execute("SELECT id_empresa FROM empresa WHERE cuit = %s;", (cuit,))
                    resultado_empresa = cursor.fetchone()

                    if resultado_empresa:
                        id_empresa = resultado_empresa[0]
                        st.toast(f"Empresa encontrada en la base de datos (ID: {id_empresa})", icon="✅")
                    else:
                        query_insert_empresa = """
                                               INSERT INTO empresa (nombre_empresa, persona_contacto, cuit, email_contacto)
                                               VALUES (%s, %s, %s, %s) RETURNING id_empresa; \
                                               """
                        cursor.execute(query_insert_empresa, (nombre_empresa, persona_contacto, cuit, email_contacto))
                        id_empresa = cursor.fetchone()[0]
                        st.toast(f"Nueva empresa registrada (ID: {id_empresa})", icon="🆕")

                    # se crea el curso, con el estado inicial: EN CURSO
                    query_insert_curso = """
                                         INSERT INTO curso (id_empresa, nombre, descripcion, cantidad_participantes, fechas_preferidas, estado)
                                         VALUES (%s, %s, %s, %s, %s, 'EN_CURSO') RETURNING id_curso; \
                                         """
                    cursor.execute(query_insert_curso, (id_empresa, tematica, descripcion, cantidad_participantes, fechas_preferidas))
                    id_curso = cursor.fetchone()[0]

                    # iniciar instancia en flowable
                    url_start = f"{FLOWABLE_URL}/runtime/process-instances"
                    payload = {
                        "processDefinitionKey": PROCESS_KEY,
                        "variables": [
                            {"name": "idCurso", "value": id_curso},
                            {"name": "idEmpresa", "value": id_empresa},
                            {"name": "nombreEmpresa", "value": nombre_empresa},
                            {"name": "tematica", "value": tematica}
                        ]
                    }

                    res = requests.post(url_start, json=payload, auth=(FLOWABLE_USER, FLOWABLE_PASS))

                    if res.status_code == 201:
                        id_instancia = res.json()["id"]

                        # vincular id de instancia con el curso
                        query_update_curso = """
                                             UPDATE curso SET id_instancia = %s WHERE id_curso = %s; \
                                             """
                        cursor.execute(query_update_curso, (id_instancia, id_curso))
                        conn.commit()

                        st.success(f"Solicitud enviada con exito, ID: {id_instancia})")
                    else:
                        conn.rollback() # si falla flowable, deshacemos los cambios en la BD
                        st.error(f"Error al iniciar el proceso en Flowable: {res.text}")

                except Exception as e:
                    conn.rollback()
                    st.error(f"Error en la base de datos: {e}")
                finally:
                    cursor.close()
                    conn.close()
            else:
                st.error("No se pudo conectar a la base de datos.")


# toda la logica del login
def autenticar_empresa(usuario, clave):
    """Valida contra la tabla cuenta_empresa. Devuelve dict de la empresa o None."""
    usuario = re.sub(r"[^0-9]", "", usuario)  # aceptamos el CUIT con o sin guiones
    if not usuario:
        return None
    conn = db_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT ce.id_empresa, ce.salt, ce.clave_hash, e.nombre_empresa
                        FROM cuenta_empresa ce JOIN empresa e ON e.id_empresa = ce.id_empresa
                        WHERE ce.usuario = %s;
                        """, (usuario,))
            fila = cur.fetchone()
    finally:
        conn.close()

    if not fila:
        return None
    id_empresa, salt, clave_hash, nombre = fila
    calculado = hashlib.sha256((salt + clave).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(calculado, clave_hash.strip()):
        return None
    return {"rol": "empresa", "id_empresa": id_empresa, "nombre": nombre, "usuario": usuario}


def autenticar_personal(usuario, clave):
    """
    Personal de la institucion (4.1.3): usan su usuario/clave de Flowable.
    Si las credenciales son validas, la API REST responde 200.
    """
    try:
        r = requests.get(f"{FLOWABLE_URL}/identity/users/{usuario}", auth=(usuario, clave), timeout=5)
    except requests.RequestException:
        return None
    if r.status_code == 200:
        datos = r.json()
        id_usuario = datos.get("id") or usuario
        nombre = " ".join(p for p in (datos.get("firstName"), datos.get("lastName")) if p) or id_usuario
        return {"rol": "personal", "usuario": id_usuario, "nombre": nombre, "clave": clave}
    return None


def pantalla_login():
    boton_volver()
    st.title("🔐 Iniciar sesion")

    with st.form("form_login"):
        usuario = st.text_input("Usuario", help="Empresas: su CUIT (con o sin guiones). Personal: su usuario de Flowable.")
        clave = st.text_input("Contraseña", type="password")
        ingresar = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

    if ingresar:
        if not usuario or not clave:
            st.error("Complete usuario y contraseña.")
            return
        try:
            datos = autenticar_empresa(usuario, clave) or autenticar_personal(usuario, clave)
        except Exception as e:
            st.error(f"No se pudo validar el usuario: {e}")
            return

        if datos is None:
            st.error("Usuario o contraseña incorrectos.")
            return

        st.session_state.usuario = datos
        st.session_state.pagina = "panel_empresa" if datos["rol"] == "empresa" else "panel_personal"
        st.rerun()

# pantalla cuando la empresa inicia sesion

def pantalla_panel_empresa():
    usuario = st.session_state.usuario
    st.title("📋 Mis cursos")
    st.caption(f"{usuario['nombre']} · usuario {usuario['usuario']}")
    st.button("Cerrar sesion", on_click=cerrar_sesion)
    st.divider()
    try:
        cursos = obtener_cursos_empresa(usuario["id_empresa"])
    except Exception as e:
        st.error(f"No se pudieron cargar los cursos: {e}")
        return
    if not cursos:
        st.info("Todavia no tiene cursos con acceso habilitado.")
        return
    st.subheader("Capacitaciones de mi empresa")
    for curso in cursos:
        with st.container(border=True):
            st.subheader(curso["nombre"])
            try:
                estado_visible = obtener_estado_curso(curso)
                st.write(f"**Estado:** {estado_visible}")
            except requests.RequestException:
                st.write("**Estado:** No disponible temporalmente")
            st.write(
                f"**Descripcion:** "
                f"{curso['descripcion'] or 'Sin descripcion'}"
            )
            st.write(
                f"**Participantes estimados:** "
                f"{curso['cantidad_participantes'] or 'No especificado'}"
            )
            st.write(
                f"**Fechas preferidas:** "
                f"{curso['fechas_preferidas'] or 'No especificadas'}"
            )
            st.caption(f"Curso N.º {curso['id_curso']}")

            if estado_visible == "En preparación" and curso["id_instancia"]:
                st.markdown("**Actividades pendientes**")
                try:
                    actividades = obtener_actividades_pendientes(
                        curso["id_instancia"]
                    )
                    if actividades:
                        for actividad in actividades:
                            st.write(f"◯ {actividad}")
                    else:
                        st.caption(
                            "No hay tareas de usuario pendientes en este momento."
                        )
                except requests.RequestException:
                    st.caption(
                        "No se pudieron consultar las actividades pendientes."
                    )

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



def form_propuesta(tarea, nombre, variables, es_revision):
    """
    Administracion:
    Registrar y elaborar una propuesta y revisar una propuesta, formularios similares, ademas completarla.

    Formulario unico para 'Propuesta' y 'Revisar'.
    """
    if es_revision:
        obs = variables.get("observaciones") or "Sin observaciones detalladas."
        st.warning(f"📝 **Observaciones de la empresa:** {obs}")

    nombre_fijo = variables.get("nombreCurso") or variables.get("tematica") or ""

    with st.form(key=f"form_propuesta_{tarea['id']}"):
        # En revision mostramos el nombre como lectura para no cambiar el curso solicitado
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


def parsear_fecha_ui(valor, defecto):
    """
    para que no haya error de tipos, ya que flowable da la fecha en formato texto, convierte texto a date
    """
    if not valor:
        return defecto
    try:
        return datetime.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return defecto


def obtener_tareas_personal(usuario, filtro):
    """
    Consulta las tareas de usuario en Flowable con las credenciales del propio usuario. 
    filtro: "assignee" (asignadas a el) o "candidateUser" (sin asignar, disponibles para el o para su grupo).
    """
    tareas = []
    inicio = 0
    while True:
        respuesta = requests.get(
            f"{FLOWABLE_URL}/runtime/tasks",
            params={
                filtro: usuario["usuario"],
                "includeProcessVariables": "true",
                "sort": "createTime",
                "order": "asc",
                "start": inicio,
                "size": 100,
            },
            auth=(usuario["usuario"], usuario["clave"]),
            timeout=10,
        )
        respuesta.raise_for_status()
        pagina = respuesta.json()
        tareas.extend(pagina.get("data", []))
        inicio += pagina.get("size", 0)
        if not pagina.get("data") or inicio >= pagina.get("total", 0):
            return tareas


# tarea que necesitan datos propios para completarse
# Completarla sin esos datos falla en el motor asi que por ahora no se ofrecen aca.
TAREAS_CON_PANTALLA_PROPIA = {
    "Activity_12i2hpf": "Se completa con la seleccion de recursos.",
}


def accion_tarea(id_tarea, nombre, accion, variables=None):
    """
    Reclama o completa una tarea en Flowable con las credenciales del usuario.
    Se usa como callback de los botones: deja el resultado en la sesion y Streamlit vuelve a dibujar el panel con las listas actualizadas.
    """
    usuario = st.session_state.usuario
    """
    si se completa una tarea y ademas tiene variables, se pasan en el cuerpo, por ejemplo los formularios de la propuesta(generar o revisar)
    """
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


def mostrar_tarea(tarea, accion):
    """
    Muestra una tarjeta con la tarea y el curso al que pertenece.
    accion: "completar" (tareas asignadas al usuario) o "reclamar" (disponibles para su grupo).
    """
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

        if accion == "completar" and task_key in ("Propuesta", "Revisar"):
            form_propuesta(tarea, nombre, variables, es_revision=(task_key == "Revisar"))
            return

        pantalla_propia = TAREAS_CON_PANTALLA_PROPIA.get(tarea.get("taskDefinitionKey"))
        if accion == "completar" and pantalla_propia:
            st.caption(f"ℹ️ {pantalla_propia} Todavia no esta disponible en el sitio.")
        else:
            st.button(
                "✅ Completar" if accion == "completar" else "✋ Reclamar",
                key=f"{accion}_{tarea['id']}",
                on_click=accion_tarea,
                args=(tarea["id"], nombre, accion),
                type="primary" if accion == "completar" else "secondary",
            )


# router: decide que pantalla dibujar
PANTALLAS = {
    "inicio": pantalla_inicio,
    "formulario": pantalla_formulario,
    "login": pantalla_login,
    "panel_empresa": pantalla_panel_empresa,
    "panel_personal": pantalla_panel_personal,
}

# Pantalla cuando la empresa inicia sesion

def obtener_cursos_empresa(id_empresa):
    """
    Obtiene los cursos de una empresa que tienen
    el acceso habilitado.
    """
    conn = db_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    id_curso,
                    nombre,
                    descripcion,
                    estado,
                    id_instancia,
                    cantidad_participantes,
                    fechas_preferidas
                FROM curso
                WHERE id_empresa = %s
                  AND acceso_habilitado = TRUE
                ORDER BY id_curso DESC;
            """, (id_empresa,))

            columnas = [col[0] for col in cursor.description]
            filas = cursor.fetchall()

            return [
                dict(zip(columnas, fila))
                for fila in filas
            ]
    finally:
        conn.close()


def obtener_actividades_activas(id_instancia):
    """
    Consulta las actividades activas de una instancia
    utilizando la API REST de Flowable.
    """
    url = f"{FLOWABLE_URL}/runtime/executions"
    respuesta = requests.get(
        url,
        params={"processInstanceId": id_instancia},
        auth=(FLOWABLE_USER, FLOWABLE_PASS),
        timeout=10
    )
    respuesta.raise_for_status()
    return respuesta.json().get("data", [])


def obtener_actividades_pendientes(id_instancia):
    """
    Devuelve los nombres de las tareas de usuario
    pendientes en una instancia.
    """
    tareas = obtener_tareas_activas(id_instancia)
    actividades = []
    for tarea in tareas:
        nombre = tarea.get("name")
        if nombre:
            actividades.append(nombre)
    return actividades


def obtener_estado_curso(curso):
    """
    Determina el estado visible del curso
    consultando PostgreSQL y Flowable.
    """

    estado_bd = curso["estado"]

    # Primero comprobar si el curso terminó
    estados_finales = {
        "FINALIZADO": "Finalizado",
        "CANCELADO": "Cancelado",
        "RECHAZADO": "Rechazado",
        "SIN_RESPUESTA": "Sin respuesta",
        "NO_VIABLE": "No viable"
    }

    if estado_bd in estados_finales:
        return estados_finales[estado_bd]

    if not curso["id_instancia"]:
        return "Estado no disponible"

    # Consultar las ejecuciones activas de Flowable
    ejecuciones = obtener_actividades_activas(
        curso["id_instancia"]
    )

    actividades = {
        ejecucion["activityId"]
        for ejecucion in ejecuciones
        if ejecucion.get("activityId")
    }

    # Etapa de preparación
    if "Preparar" in actividades:
        return "En preparación"

    # Etapa de elaboración del informe
    if "Informe" in actividades or "EnviarInforme" in actividades:
        return "En elaboración del informe"

    # Etapa de desarrollo
    if "Dictar" in actividades:
        return "En desarrollo"

    # Curso confirmado, pero todavía sin comenzar
    if (
        "Confirmar" in actividades
        or "Activity_1018bdz" in actividades
    ):
        return "Confirmado y pendiente de inicio"

    # No se pudo identificar la actividad actual
    return "Estado no disponible"



def obtener_tareas_activas(id_instancia):
    """
    Consulta las tareas de usuario pendientes
    de una instancia de Flowable.
    """
    url = f"{FLOWABLE_URL}/runtime/tasks"
    respuesta = requests.get(
        url,
        params={
            "processInstanceId": id_instancia,
            "size": 100
        },
        auth=(FLOWABLE_USER, FLOWABLE_PASS),
        timeout=10
    )
    respuesta.raise_for_status()
    return respuesta.json().get("data", [])


def obtener_definicion_instancia(id_instancia):
    """
    Obtiene la definición BPMN utilizada
    por una instancia de Flowable.
    """
    url = f"{FLOWABLE_URL}/runtime/process-instances/{id_instancia}"

    respuesta = requests.get(
        url,
        auth=(FLOWABLE_USER, FLOWABLE_PASS),
        timeout=10
    )

    respuesta.raise_for_status()

    return respuesta.json()

# Proteger las pantallas privadas: sin sesion, se manda al login
pagina = st.session_state.pagina
if pagina.startswith("panel_") and st.session_state.usuario is None:
    pagina = "login"

PANTALLAS[pagina]()