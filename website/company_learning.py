import streamlit as st
import psycopg2
import requests

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
st.set_page_config(page_title="Solicitud de Capacitacion", page_icon="🏢", layout="centered")

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
                        VALUES (%s, %s, %s, %s) RETURNING id_empresa;
                    """
                    cursor.execute(query_insert_empresa, (nombre_empresa, persona_contacto, cuit, email_contacto))
                    id_empresa = cursor.fetchone()[0]
                    st.toast(f"Nueva empresa registrada (ID: {id_empresa})", icon="🆕")

                # se crea el curso, con el estado inicial: EN CURSO
                query_insert_curso = """
                    INSERT INTO curso (id_empresa, nombre, descripcion, cantidad_participantes, fechas_preferidas, estado)
                    VALUES (%s, %s, %s, %s, %s, 'EN_CURSO') RETURNING id_curso;
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
                        UPDATE curso SET id_instancia = %s WHERE id_curso = %s;
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