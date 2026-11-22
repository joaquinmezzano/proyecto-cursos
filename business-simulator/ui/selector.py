import streamlit as st

from formato import etiqueta_instancia
from services import db, flowable


def _obtener_instancias():
    try:
        return flowable.obtener_instancias()
    except Exception as e:
        st.error(f"Error de conexión con Flowable: {e}")
    return []


def _obtener_datos_cursos(ids_instancia):
    try:
        return db.obtener_datos_cursos(ids_instancia)
    except Exception as e:
        st.warning(f"No se pudo consultar la base de datos: {e}")
        return {}


# Paso 1: devuelve el ID de la instancia elegida (frena la página si no hay ninguna)
def seleccionar_instancia():
    st.subheader("1️⃣ Seleccioná la propuesta activa")
    instancias = _obtener_instancias()

    if not instancias:
        st.info("No hay procesos en ejecución actualmente.")
        st.stop()  # Frena la pagina

    # El selector guarda el ID de la instancia, pero muestra el curso y la empresa
    datos_cursos = _obtener_datos_cursos([i["id"] for i in instancias])
    etiquetas = {i["id"]: etiqueta_instancia(i, datos_cursos) for i in instancias}
    return st.selectbox(
        "Propuestas disponibles:",
        options=list(etiquetas.keys()),
        format_func=lambda id_inst: etiquetas[id_inst],
    )
