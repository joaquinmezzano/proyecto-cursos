import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import psycopg2

FLOWABLE_URL = "http://localhost:8080/flowable-ui/process-api"
AUTH = HTTPBasicAuth("admin", "test")

DB_CONFIG = {
    "host": "localhost",
    "port": 5434,
    "dbname": "institucion",
    "user": "flowable",
    "password": "flow10",
}

st.button("🔄 Actualizar", use_container_width=True)
st.set_page_config(page_title="Empresa", page_icon="🏢")
st.title("🏢 Cliente de la Empresa")

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

# Busca en la base el curso y la empresa asociados a cada instancia
# Devuelve un diccionario {id_instancia: (nombre_curso, nombre_empresa)}
def obtener_datos_cursos(ids_instancia):
    if not ids_instancia:
        return {}
    try:
        with psycopg2.connect(**DB_CONFIG) as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT c.id_instancia, c.nombre, e.nombre_empresa
                FROM curso c
                JOIN empresa e ON e.id_empresa = c.id_empresa
                WHERE c.id_instancia = ANY(%s)
            """, (list(ids_instancia),))
            return {fila[0]: (fila[1], fila[2]) for fila in cur.fetchall()}
    except Exception as e:
        st.warning(f"No se pudo consultar la base de datos: {e}")
        return {}

# Arma el texto que se ve en el selector para cada instancia
def etiqueta_instancia(instancia, datos_cursos):
    inicio = instancia["startTime"][:10]
    inicio = f"{inicio[8:10]}/{inicio[5:7]}/{inicio[0:4]}"
    datos = datos_cursos.get(instancia["id"])
    if datos:
        nombre_curso, nombre_empresa = datos
        return f"{nombre_curso} — {nombre_empresa} (iniciado el {inicio})"
    # Todavía no hay curso registrado en la base
    return f"Solicitud sin propuesta registrada (iniciada el {inicio}) · ID {instancia['id']}"

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

# Detecta qué acciones tiene habilitadas la instancia en este momento
def obtener_estado_acciones(instance_id):
    estado = {
        "esperando_respuesta": False,
        "esperando_nomina": False,
        "puede_cancelar": False,
    }
    try:
        # 1. Verificar si está esperando respuesta a la propuesta
        r_aceptar = requests.get(
            f"{FLOWABLE_URL}/runtime/executions?processInstanceId={instance_id}&messageEventSubscriptionName=Aceptación",
            auth=AUTH,
        )
        if r_aceptar.status_code == 200 and r_aceptar.json().get("data"):
            estado["esperando_respuesta"] = True

        # 2. Verificar si está esperando la nómina (Receive Task id="Nomina")
        r_nomina = requests.get(
            f"{FLOWABLE_URL}/runtime/executions?processInstanceId={instance_id}&activityId=Nomina",
            auth=AUTH,
        )
        if r_nomina.status_code == 200 and r_nomina.json().get("data"):
            estado["esperando_nomina"] = True

        # 3. Verificar si está dentro del subproceso donde se puede cancelar
        r_cancelar = requests.get(
            f"{FLOWABLE_URL}/runtime/executions?processInstanceId={instance_id}&messageEventSubscriptionName=Cancelación",
            auth=AUTH,
        )
        if r_cancelar.status_code == 200 and r_cancelar.json().get("data"):
            estado["puede_cancelar"] = True

    except Exception as e:
        st.error(f"Error consultando estado de la instancia: {e}")

    return estado

# envio de mensaje, dependiendo si es modificar, aceptar, rechazar o cancelar.
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
            st.success(f"Se envió la respuesta, el evento es: {msg_name}")
        else:
            st.error(f"Error: {res_put.text}")
    else:
        # Si no lo encuentra, el token esta en otro lado
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
            st.success("Se envió la nómina de participantes")
        else:
            st.error(f"Error: {res_put.text}")
    else:
        # Si no la encuentra (ej: la propuesta todavía no fue aceptada o la nómina ya se envió)
        st.warning("⚠️ La instancia seleccionada NO está esperando la nómina en este momento.")

# Interfaz grafica
st.subheader("1️⃣ Seleccioná la propuesta activa")
instancias = obtener_instancias()

if not instancias:
    st.info("No hay procesos en ejecución actualmente.")
    st.stop()  # Frena la pagina

# El selector guarda el ID de la instancia, pero muestra el curso y la empresa
datos_cursos = obtener_datos_cursos([i["id"] for i in instancias])
etiquetas = {i["id"]: etiqueta_instancia(i, datos_cursos) for i in instancias}
instance_id = st.selectbox(
    "Propuestas disponibles:",
    options=list(etiquetas.keys()),
    format_func=lambda id_inst: etiquetas[id_inst],
)

# Descargar pdf asi el cliente de la empresa lo analiza
st.markdown("### 📄 Documento de la propuesta seleccionada")
pdf_bytes = descargar_pdf(instance_id)

if pdf_bytes:
    st.download_button(
        label="📥 Descargar Propuesta Comercial (PDF)",
        data=pdf_bytes,
        file_name=f"Propuesta_{instance_id}.pdf",
        mime="application/pdf"
    )
    with st.expander("️Previsualizar propuesta", expanded=True):
            st.pdf(pdf_bytes, height=600)
else:
    st.info("El documento PDF no está disponible para la instancia seleccionada")

# Consultar en qué fase está la instancia seleccionada
estado = obtener_estado_acciones(instance_id)

# Si todavía no llegó a la espera de mensajes ni al subproceso, solo se muestra el paso 1
if not (estado["esperando_respuesta"] or estado["esperando_nomina"] or estado["puede_cancelar"]):
    st.info("⏳ La solicitud está siendo procesada por la institución. Aún no hay acciones disponibles para la empresa.")
    st.stop()

st.subheader("2️⃣ Acciones disponibles en este momento")

# FASE A: Esperando respuesta sobre la propuesta (Aceptar, Rechazar, Modificar)
if estado["esperando_respuesta"]:
    tab_aceptar, tab_rechazar, tab_modificar = st.tabs([
        "✔ Aceptar", "✖ Rechazar", "✏ Modificar"
    ])

    with tab_aceptar:
        st.write("Aceptar la propuesta comercial en las condiciones y fechas propuestas por la administración.")
        if st.button("Confirmar Aceptación", type="primary"):
            enviar_mensaje(instance_id, "Aceptación")

    with tab_rechazar:
        st.write("Rechazar la propuesta y finalizar el trámite.")
        if st.button("Rechazar Propuesta", type="primary"):
            enviar_mensaje(instance_id, "Rechazo")

    with tab_modificar:
        st.write("Solicitar cambios en el presupuesto, fechas o programa.")
        obs = st.text_area("Observaciones:")
        if st.button("Enviar Observaciones", type="primary"):
            if obs.strip():
                enviar_mensaje(instance_id, "Solicitud de modificaciones", [{"name": "observaciones", "value": obs.strip()}])
            else:
                st.error("Por favor, escribí las observaciones.")

# FASE B: Dentro del subproceso de preparación (Nómina si falta + Cancelar siempre disponible)
elif estado["esperando_nomina"] or estado["puede_cancelar"]:
    nombres_tabs = []
    if estado["esperando_nomina"]:
        nombres_tabs.append("📋 Enviar Nómina")
    if estado["puede_cancelar"]:
        nombres_tabs.append("🚫 Cancelar")

    tabs = st.tabs(nombres_tabs)
    idx = 0

    if estado["esperando_nomina"]:
        with tabs[idx]:
            st.write("Enviar la nómina de participantes del curso.")
            nomina = st.text_area("Lista de participantes (para mayor entendimiento podria ser formato 'Apellido, Nombre')")
            if st.button("Enviar Nómina", type="primary"):
                if nomina.strip():
                    enviar_nomina(instance_id, nomina.strip())
                else:
                    st.error("Por favor, ingresá la nómina.")
        idx += 1

    if estado["puede_cancelar"]:
        with tabs[idx]:
            st.write("Cancelar el curso durante la fase de preparación.")
            if st.button("Solicitar Cancelación", type="primary"):
                enviar_mensaje(instance_id, "Cancelación")