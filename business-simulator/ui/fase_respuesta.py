# FASE A: Esperando respuesta sobre la propuesta (Aceptar, Rechazar, Modificar)
import streamlit as st

from formato import fecha_dd_mm_aaaa, texto_recordatorio
from services import flowable
from ui.mensajes import enviar_mensaje


def _obtener_fechas_propuestas(instance_id):
    try:
        return flowable.obtener_fechas_propuestas(instance_id)
    except Exception as e:
        st.warning(f"No se pudieron leer las variables de fecha: {e}")
    return "", "", ""


def mostrar_fase_respuesta(instance_id):
    # Recordatorios que envio la institucion porque la propuesta sigue sin respuesta
    recordatorio = texto_recordatorio(flowable.obtener_variables_recordatorio(instance_id))
    if recordatorio:
        st.warning(recordatorio, icon="📨")

    tab_aceptar, tab_rechazar, tab_modificar = st.tabs([
        "✔ Aceptar", "✖ Rechazar", "✏ Modificar"
    ])

    with tab_aceptar:
        _tab_aceptar(instance_id)

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


def _tab_aceptar(instance_id):
    f1, f2, otras = _obtener_fechas_propuestas(instance_id)

    def a_iso_flowable(fecha_str):
        if len(fecha_str) == 10:
            return f"{fecha_str}T09:00:00-03:00"
        return fecha_str

    if otras:
        st.info(
            f"Otras fechas {otras}\n\n"
            "Si preferís alguna de estas opciones alternativas, usá la opcion Modificar para pedir el cambio."
        )

    fecha_base = None

    # Caso 2: Vinieron 2 fechas -> la empresa elige una
    if f1 and f2:
        st.write("La administración propuso **2 fechas posibles**. Seleccioná la fecha con la que aceptás el curso:")
        fecha_base = st.radio(
            "Fechas disponibles:",
            options=[f1, f2],
            format_func=lambda f: f"📅 {fecha_dd_mm_aaaa(f)} ({f})",
        )

    # Caso 1 y 3: Vino 1 sola fecha -> se toma esa fecha directamente
    elif f1:
        st.write(f"📅 **Fecha propuesta por la administración:** `{fecha_dd_mm_aaaa(f1)}`")
        fecha_base = f1

    else:
        st.error("No se encontró 'fechaposible1' en la instancia.")

    # Selector de hora exacto para que la empresa ponga un horario tambien para probar el timer
    if fecha_base:
        hora = st.time_input("🕒 Hora de inicio del curso:", step=60)
        fecha_iso = f"{fecha_base[:10]}T{hora.strftime('%H:%M:%S')}-03:00"

        if st.button("Confirmar Aceptación", type="primary"):
            enviar_mensaje(
                instance_id,
                "Aceptación",
                [{"name": "fechaCurso", "type": "string", "value": fecha_iso}],
            )
