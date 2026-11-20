import streamlit as st

def ir_a(pagina):
    st.session_state.pagina = pagina

def cerrar_sesion():
    st.session_state.usuario = None
    st.session_state.pagina = "inicio"

def boton_volver():
    st.button("⬅ Volver al inicio", on_click=ir_a, args=("inicio",))