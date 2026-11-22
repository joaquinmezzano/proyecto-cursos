import psycopg2

from config import DB_CONFIG


# Busca en la base el curso y la empresa asociados a cada instancia
# Devuelve un diccionario {id_instancia: (nombre_curso, nombre_empresa)}
def obtener_datos_cursos(ids_instancia):
    if not ids_instancia:
        return {}
    with psycopg2.connect(**DB_CONFIG) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.id_instancia, c.nombre, e.nombre_empresa
            FROM curso c
            JOIN empresa e ON e.id_empresa = c.id_empresa
            WHERE c.id_instancia = ANY(%s)
        """, (list(ids_instancia),))
        return {fila[0]: (fila[1], fila[2]) for fila in cur.fetchall()}
