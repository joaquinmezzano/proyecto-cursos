# Acceso a la API REST de Flowable. No usa Streamlit: devuelve datos o resultados
# y la interfaz (ui/) decide qué mostrar.
import requests

from config import FLOWABLE_URL, AUTH

# Resultados posibles de enviar_mensaje / enviar_nomina
ENVIADO = "enviado"
ERROR = "error"
NO_ESPERANDO = "no_esperando"


# Consulta a flowable cuales son las instancias que están en ejecución
def obtener_instancias():
    url = f"{FLOWABLE_URL}/runtime/process-instances?processDefinitionKey=Process_Curso"
    resp = requests.get(url, auth=AUTH)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []


# Ejecuciones de la instancia que esperan un mensaje o están paradas en una actividad
def buscar_ejecuciones(instance_id, mensaje=None, actividad=None):
    url = f"{FLOWABLE_URL}/runtime/executions?processInstanceId={instance_id}"
    if mensaje:
        url += f"&messageEventSubscriptionName={mensaje}"
    if actividad:
        url += f"&activityId={actividad}"
    res = requests.get(url, auth=AUTH)
    if res.status_code == 200:
        return res.json().get("data") or []
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


# Lee fechaposible1, fechaposible2 y otrasfechasopcional guardadas por Administración
def obtener_fechas_propuestas(instance_id):
    url = f"{FLOWABLE_URL}/runtime/process-instances/{instance_id}/variables"
    res = requests.get(url, auth=AUTH)
    if res.status_code == 200:
        vars_dict = {v["name"]: v["value"] for v in res.json()}
        f1 = str(vars_dict.get("fechaposible1") or "").strip()
        f2 = str(vars_dict.get("fechaposible2") or "").strip()
        otras = str(vars_dict.get("otrasfechasopcional") or "").strip()
        return f1, f2, otras
    return "", "", ""


# Variables del proceso para el recordatorio (o None si Flowable no responde)
def obtener_variables_recordatorio(instance_id):
    try:
        res = requests.get(f"{FLOWABLE_URL}/runtime/process-instances/{instance_id}/variables",
                           auth=AUTH, timeout=10)
        if res.status_code != 200:
            return None
    except requests.RequestException:
        return None
    return {v["name"]: v.get("value") for v in res.json()}


# Detecta qué acciones tiene habilitadas la instancia en este momento
# Devuelve (estado, error): si una consulta falla, el estado queda con lo que se llegó a verificar
def obtener_estado_acciones(instance_id):
    estado = {
        "esperando_respuesta": False,
        "esperando_nomina": False,
        "puede_cancelar": False,
    }
    try:
        # 1. Verificar si está esperando respuesta a la propuesta
        if buscar_ejecuciones(instance_id, mensaje="Aceptación"):
            estado["esperando_respuesta"] = True

        # 2. Verificar si está esperando la nómina (Receive Task id="Nomina")
        if buscar_ejecuciones(instance_id, actividad="Nomina"):
            estado["esperando_nomina"] = True

        # 3. Verificar si está dentro del subproceso donde se puede cancelar
        if buscar_ejecuciones(instance_id, mensaje="Cancelación"):
            estado["puede_cancelar"] = True

    except Exception as e:
        return estado, e

    return estado, None


# Dispara la ejecución con el payload dado. Devuelve (resultado, detalle)
def _disparar(ejecuciones, payload):
    if not ejecuciones:
        # Si no lo encuentra, el token esta en otro lado
        return NO_ESPERANDO, None
    exec_id = ejecuciones[0]["id"]
    res_put = requests.put(f"{FLOWABLE_URL}/runtime/executions/{exec_id}", json=payload, auth=AUTH)
    if res_put.status_code in [200, 204]:
        return ENVIADO, None
    return ERROR, res_put.text


# envio de mensaje, dependiendo si es modificar, aceptar, rechazar o cancelar.
def enviar_mensaje(instance_id, msg_name, variables=None):
    if variables is None: variables = []
    payload = {
        "action": "messageEventReceived",
        "messageName": msg_name,
        "variables": variables
    }
    return _disparar(buscar_ejecuciones(instance_id, mensaje=msg_name), payload)


# envio de la nomina de participantes
# "Recibir nómina" es una receive task (no un evento de mensaje), por eso no se usa
# messageEventReceived: se busca la ejecución que está esperando en esa tarea y se la dispara con "trigger"
def enviar_nomina(instance_id, nomina):
    payload = {
        "action": "trigger",
        "variables": [{"name": "nominaParticipantes", "type": "string", "value": nomina}]
    }
    return _disparar(buscar_ejecuciones(instance_id, actividad="Nomina"), payload)
