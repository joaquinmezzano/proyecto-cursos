# FASE B: Dentro del subproceso de preparación (Nómina si falta + Cancelar siempre disponible)
import streamlit as st

from ui.mensajes import enviar_mensaje, enviar_nomina


def mostrar_fase_preparacion(instance_id, estado):
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
