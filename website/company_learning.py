import streamlit as st
import psycopg2
import requests
import hashlib
import hmac
import re

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
        return {"rol": "personal", "usuario": usuario, "nombre": usuario}
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
    st.info("Pendiente: listado de cursos, estado y actividades en preparacion (4.1.2).")

# pantalla cuando un usuario inicia sesion
def pantalla_panel_personal():
    usuario = st.session_state.usuario
    st.title("🧑‍💼 Panel del personal")
    st.caption(f"Usuario: {usuario['usuario']}")
    st.button("Cerrar sesion", on_click=cerrar_sesion)
    st.info("Pendiente: funciones de Administracion y del Equipo Docente (4.1.3 / 4.1.4).")


# router: decide que pantalla dibujar
PANTALLAS = {
    "inicio": pantalla_inicio,
    "formulario": pantalla_formulario,
    "login": pantalla_login,
    "panel_empresa": pantalla_panel_empresa,
    "panel_personal": pantalla_panel_personal,
}

# Proteger las pantallas privadas: sin sesion, se manda al login
pagina = st.session_state.pagina
if pagina.startswith("panel_") and st.session_state.usuario is None:
    pagina = "login"

PANTALLAS[pagina]()