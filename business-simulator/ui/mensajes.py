# Muestra el resultado de un envío a Flowable
import streamlit as st

from services import flowable


def mostrar_envio(resultado, detalle, texto_exito, texto_no_esperando):
    if resultado == flowable.ENVIADO:
        st.success(texto_exito)
    elif resultado == flowable.ERROR:
        st.error(f"Error: {detalle}")
    else:
        st.warning(texto_no_esperando)


def enviar_mensaje(instance_id, msg_name, variables=None):
    resultado, detalle = flowable.enviar_mensaje(instance_id, msg_name, variables)
    mostrar_envio(
        resultado, detalle,
        f"Se envió la respuesta, el evento es: {msg_name}",
        f"⚠️ La instancia seleccionada NO está esperando la acción '{msg_name}' en este momento.",
    )


def enviar_nomina(instance_id, nomina):
    resultado, detalle = flowable.enviar_nomina(instance_id, nomina)
    # Si no la encuentra (ej: la propuesta todavía no fue aceptada o la nómina ya se envió)
    mostrar_envio(
        resultado, detalle,
        "Se envió la nómina de participantes",
        "⚠️ La instancia seleccionada NO está esperando la nómina en este momento.",
    )
