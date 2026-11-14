import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

FLOWABLE_URL = "http://localhost:8080/flowable-ui/process-api"
AUTH = HTTPBasicAuth("admin", "test")

st.set_page_config(page_title="Empresa", page_icon="🏢")
st.title("🏢 CLiente de la Empresa")
st.markdown("Simulador de respuestas para la API REST de Flowable")

# Consulta a flowable cuales son las instancias que están en ejecución
def obtener_instancias():
    url = f"{FLOWABLE_URL}/runtime/process-instances?processDefinitionKey=Process_Curso"
    try:
        resp = requests.get(url, auth=AUTH)
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception as e:
        st.error(f"Error de conexión con Flowable: {e}")
    return []

# dada la instancia del proceso descargar el pdf
def descargar_pdf(instance_id):
    url = f"{FLOWABLE_URL}/runtime/process-instances/{instance_id}/variables/pdfPropuesta/data"
    try:
        res = requests.get(url, auth=AUTH)
        if res.status_code == 200:
            return res.content
    except:
        pass
    return None  # Si la variable no existe pj proceso recién iniciado que no llego a generar pdf, devuelve None

# envio de mensaje, dependiendo si es modificar, aceptar o rechazar
def enviar_mensaje(instance_id, msg_name, variables=None):
    if variables is None: variables = []

    url_exec = f"{FLOWABLE_URL}/runtime/executions?processInstanceId={instance_id}&messageEventSubscriptionName={msg_name}"
    res_exec = requests.get(url_exec, auth=AUTH)

    if res_exec.status_code == 200 and res_exec.json().get("data"):
        exec_id = res_exec.json()["data"][0]["id"]

        url_post = f"{FLOWABLE_URL}/runtime/executions/{exec_id}"
        payload = {
            "action": "messageEventReceived",
            "messageName": msg_name,
            "variables": variables
        }
        res_put = requests.put(url_post, json=payload, auth=AUTH)

        if res_put.status_code in [200, 204]:
            st.success(f"Se envió la respuesta a Flowable, el evento es: {msg_name})")
            st.balloons()
        else:
            st.error(f"Error en Flowable: {res_put.text}")
    else:
        # Si no lo encuentra (ej: tocó "Aceptar" pero está en la fase de preparación)
        st.warning(f"⚠️ La instancia seleccionada NO está esperando la acción '{msg_name}' en este momento.")


# envio de la nomina de participantes
# "Recibir nómina" es una receive task (no un evento de mensaje), por eso no se usa
# messageEventReceived: se busca la ejecución que está esperando en esa tarea y se la dispara con "trigger"
def enviar_nomina(instance_id, nomina):
    url_exec = f"{FLOWABLE_URL}/runtime/executions?processInstanceId={instance_id}&activityId=Nomina"
    res_exec = requests.get(url_exec, auth=AUTH)

    if res_exec.status_code == 200 and res_exec.json().get("data"):
        exec_id = res_exec.json()["data"][0]["id"]

        url_put = f"{FLOWABLE_URL}/runtime/executions/{exec_id}"
        payload = {
            "action": "trigger",
            "variables": [{"name": "nominaParticipantes", "type": "string", "value": nomina}]
        }
        res_put = requests.put(url_put, json=payload, auth=AUTH)

        if res_put.status_code in [200, 204]:
            st.success("Se envió la nómina de participantes a Flowable")
            st.balloons()
        else:
            st.error(f"Error en Flowable: {res_put.text}")
    else:
        # Si no la encuentra (ej: la propuesta todavía no fue aceptada o la nómina ya se envió)
        st.warning("⚠️ La instancia seleccionada NO está esperando la nómina en este momento.")




# Interfaz grafica
st.subheader("1️⃣ Seleccioná tu trámite activo")
instancias = obtener_instancias()

if not instancias:
    st.info("No hay procesos en ejecución actualmente. inicia uno desde Flowable .")
    st.stop()  # Frena la pagina

# Diccionario solo para visual
opciones = {f"Instancia ID: {i['id']} (Iniciada: {i['startTime'][:10]})": i['id'] for i in instancias}
seleccion = st.selectbox("Trámites disponibles:", list(opciones.keys()))
instance_id = opciones[seleccion]

# Descargar pdf asi el cliente de la empresa lo analiza
st.markdown("### 📄 Documento de la Propuesta")
pdf_bytes = descargar_pdf(instance_id)

if pdf_bytes:
    st.download_button(
        label="📥 Descargar Propuesta Comercial (PDF)",
        data=pdf_bytes,
        file_name=f"Propuesta_{instance_id}.pdf",
        mime="application/pdf"
    )
else:
    st.info("El documento PDF aún no está disponible para esta instancia, el proceso podría estar antes")

st.divider()

# Acciones, y sus distintas opciones
st.subheader("2️⃣ Dada la propuesta, ¿Que queres hacer?")

tab_aceptar, tab_rechazar, tab_modificar, tab_nomina, tab_cancelar = st.tabs([
    "✔ Aceptar", "✖ Rechazar", "✏ Modificar", "📋 Enviar Nómina", "🚫 Cancelar"
])

# Opcion aceptar: la empresa acepta e informa la fecha acordada de inicio del curso
with tab_aceptar:
    st.write("Aceptar la propuesta indicando la fecha acordada de inicio del curso.")
    fecha = st.date_input("Fecha acordada")
    hora = st.time_input("Hora de inicio", step=60)
    if st.button("Confirmar Aceptación", type="primary"):
        # Formato ISO 8601 con zona horaria de Argentina, que es lo que entiende el timer de Flowable
        fecha_curso = f"{fecha.isoformat()}T{hora.strftime('%H:%M:%S')}-03:00"
        enviar_mensaje(instance_id, "Aceptación",
                       [{"name": "fechaCurso", "type": "string", "value": fecha_curso}])

# # Opcion rechazar
with tab_rechazar:
    st.write("Rechazar la propuesta y finalizar el trámite.")
    if st.button("Rechazar Propuesta", type="primary"):
        enviar_mensaje(instance_id, "Rechazo")

# Opcion modificar, caso exclusivo:
# donde la api externa manda observaciones hacia flowable, para que el jefe administrativo vea que campos modificar si asi lo quiere
with tab_modificar:
    st.write("Solicitar cambios en el presupuesto o programa.")
    obs = st.text_area("Observaciones:")
    if st.button("Enviar Observaciones", type="primary"):
        if obs:
            enviar_mensaje(instance_id, "Solicitud de modificaciones", [{"name": "observaciones", "value": obs}])
        else:
            st.error("Por favor, escribí las observaciones.")

# Opcion cancelar
with tab_cancelar:
    st.write("Cancelar el curso durante la fase de preparación.")
    if st.button("Solicitar Cancelación de Emergencia", type="primary"):
        enviar_mensaje(instance_id, "Cancelación")

# Opcion nomina: la empresa envía la lista de participantes durante la preparación del curso
with tab_nomina:
    st.write("Enviar la nómina de participantes del curso.")
    nomina = st.text_area("Lista de participantes (separados por coma):")
    if st.button("Enviar Nómina", type="primary"):
        if nomina.strip():
            enviar_nomina(instance_id, nomina.strip())
        else:
            st.error("Por favor, ingresá la nómina.")