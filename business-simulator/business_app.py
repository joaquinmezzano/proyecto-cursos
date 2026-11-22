import streamlit as st

from services import flowable
from ui.documento import mostrar_documento
from ui.fase_preparacion import mostrar_fase_preparacion
from ui.fase_respuesta import mostrar_fase_respuesta
from ui.selector import seleccionar_instancia

st.button("🔄 Actualizar", use_container_width=True)
st.set_page_config(page_title="Empresa", page_icon="🏢")
st.title("🏢 Cliente de la Empresa")

instance_id = seleccionar_instancia()
mostrar_documento(instance_id)

# Consultar en qué fase está la instancia seleccionada
estado, error = flowable.obtener_estado_acciones(instance_id)
if error:
    st.error(f"Error consultando estado de la instancia: {error}")

# Si todavía no llegó a la espera de mensajes ni al subproceso, solo se muestra el paso 1
if not (estado["esperando_respuesta"] or estado["esperando_nomina"] or estado["puede_cancelar"]):
    st.info("⏳ La solicitud está siendo procesada por la institución. Aún no hay acciones disponibles para la empresa.")
    st.stop()

st.subheader("2️⃣ Acciones disponibles en este momento")

if estado["esperando_respuesta"]:
    mostrar_fase_respuesta(instance_id)
elif estado["esperando_nomina"] or estado["puede_cancelar"]:
    mostrar_fase_preparacion(instance_id, estado)
