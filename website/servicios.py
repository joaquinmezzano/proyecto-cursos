import hashlib
import hmac
import re

import psycopg2
import requests

# configuracion flowable y bdd de institucion
FLOWABLE_URL = "http://localhost:8080/flowable-ui/process-api"
FLOWABLE_USER = "admin"
FLOWABLE_PASS = "test"
PROCESS_KEY = "Process_Curso"
GRUPO_DOCENTES = "docentes"

DB_HOST = "localhost"
DB_PORT = "5434"
DB_NAME = "institucion"
DB_USER = "flowable"
DB_PASS = "flow10"

VAR_PDF_INFORME = "pdfInforme"
VAR_RESUMEN_INFORME = "informeResultados"

# todo lo que seria la base de datos y funciones que se conecten a ella
def db_conexion():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def obtener_solicitud(id_curso, id_instancia):
    """
    Devuelve los datos que cargo la empresa en el formulario de solicitud.
    Se busca por variable idCurso de la instancia; si no esta, por id_instancia.
    """
    consulta = """
               SELECT e.nombre_empresa, e.cuit, e.persona_contacto, e.email_contacto,
                      c.id_curso, c.nombre, c.descripcion, c.cantidad_participantes, c.fechas_preferidas
               FROM curso c JOIN empresa e ON e.id_empresa = c.id_empresa
               WHERE {condicion};
               """
    if id_curso is not None:
        condicion, parametro = "c.id_curso = %s", int(id_curso)
    elif id_instancia:
        condicion, parametro = "c.id_instancia = %s", id_instancia
    else:
        return None

    conn = db_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute(consulta.format(condicion=condicion), (parametro,))
            fila = cur.fetchone()
            if not fila:
                return None
            columnas = [col[0] for col in cur.description]
            return dict(zip(columnas, fila))
    finally:
        conn.close()

def obtener_cursos_empresa(id_empresa):
    """Obtiene los cursos de una empresa que tienen el acceso habilitado"""
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

def guardar_informe_bd(id_instancia, resumen):
    """Deja el informe de resultados en el curso de la base de la institucion"""
    conn = db_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE curso SET informe_resultados = %s WHERE id_instancia = %s;",
                        (resumen, id_instancia))
        conn.commit()
    finally:
        conn.close()

# autentificacion de la empresa y del personal
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
    """Para ingresar se usa usuario/clave de Flowable."""
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


# todo lo que seria conexiones/peticiones a flowable

# devuelve los integrantes del grupo 'docentes' de flowable.
def obtener_docentes():
    respuesta = requests.get(
        f"{FLOWABLE_URL}/identity/users",
        params={"memberOfGroup": GRUPO_DOCENTES, "size": 100, "sort": "id"},
        auth=(FLOWABLE_USER, FLOWABLE_PASS),
        timeout=10,
    )
    respuesta.raise_for_status()
    return respuesta.json().get("data", [])

def obtener_tareas_personal(usuario, filtro):
    """Consulta las tareas de usuario en flowable con las credenciales del propio usuario"""
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

def obtener_tareas_activas(id_instancia):
    """Consulta las tareas de usuario pendientes de una instancia de flowable"""
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

def obtener_actividades_activas(id_instancia):
    """Consulta las actividades activas de una instancia utilizando la API REST de flowable"""
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
    """Devuelve los nombres de las tareas de usuario pendientes en una instancia"""
    tareas = obtener_tareas_activas(id_instancia)
    actividades = []
    for tarea in tareas:
        nombre = tarea.get("name")
        if nombre:
            actividades.append(nombre)
    return actividades

def guardar_pdf_informe(id_instancia, contenido, usuario):
    """Guarda (o reemplaza) el PDF del informe como variable binaria de la instancia"""
    respuesta = requests.put(
        f"{FLOWABLE_URL}/runtime/process-instances/{id_instancia}/variables",
        files={"file": ("informe.pdf", contenido, "application/pdf")},
        data={"name": VAR_PDF_INFORME, "type": "binary"},
        auth=(usuario["usuario"], usuario["clave"]),
        timeout=20,
    )
    respuesta.raise_for_status()

def descargar_pdf_informe(id_instancia, usuario):
    """Devuelve los bytes del PDF del informe, o None si la instancia no tiene uno cargado"""
    respuesta = requests.get(
        f"{FLOWABLE_URL}/runtime/process-instances/{id_instancia}/variables/{VAR_PDF_INFORME}/data",
        auth=(usuario["usuario"], usuario["clave"]),
        timeout=20,
    )
    if respuesta.status_code == 404:
        return None
    respuesta.raise_for_status()
    return respuesta.content