import requests
import streamlit as st

from navegacion import cerrar_sesion
from servicios import obtener_actividades_activas, obtener_actividades_pendientes, obtener_cursos_empresa

# todo lo que veria un usuario de la empresa una vez logueado
def pantalla_panel_empresa():
    usuario = st.session_state.usuario
    st.title("📋 Mis cursos")
    st.caption(f"{usuario['nombre']} · usuario {usuario['usuario']}")
    st.button("Cerrar sesion", on_click=cerrar_sesion)
    st.divider()
    try:
        cursos = obtener_cursos_empresa(usuario["id_empresa"])
    except Exception as e:
        st.error(f"No se pudieron cargar los cursos: {e}")
        return
    if not cursos:
        st.info("Todavia no tiene cursos con acceso habilitado.")
        return
    st.subheader("Capacitaciones de mi empresa")
    for curso in cursos:
        with st.container(border=True):
            st.subheader(curso["nombre"])
            try:
                estado_visible = obtener_estado_curso(curso)
                st.write(f"**Estado:** {estado_visible}")
            except requests.RequestException:
                st.write("**Estado:** No disponible temporalmente")
            st.write(
                f"**Descripcion:** "
                f"{curso['descripcion'] or 'Sin descripcion'}"
            )
            st.write(
                f"**Participantes estimados:** "
                f"{curso['cantidad_participantes'] or 'No especificado'}"
            )
            st.write(
                f"**Fechas preferidas:** "
                f"{curso['fechas_preferidas'] or 'No especificadas'}"
            )
            st.caption(f"Curso N.º {curso['id_curso']}")

            if estado_visible == "En preparación" and curso["id_instancia"]:
                st.markdown("**Actividades pendientes**")
                try:
                    actividades = obtener_actividades_pendientes(
                        curso["id_instancia"]
                    )
                    if actividades:
                        for actividad in actividades:
                            st.write(f"◯ {actividad}")
                    else:
                        st.caption(
                            "No hay tareas de usuario pendientes en este momento."
                        )
                except requests.RequestException:
                    st.caption(
                        "No se pudieron consultar las actividades pendientes."
                    )

def obtener_estado_curso(curso):
    """Determina el estado visible del curso consultando postgresql y flowable"""
    estado_bd = curso["estado"]

    # primero comprobar si el curso terminó
    estados_finales = {
        "FINALIZADO": "Finalizado",
        "CANCELADO": "Cancelado",
        "RECHAZADO": "Rechazado",
        "SIN_RESPUESTA": "Sin respuesta",
        "NO_VIABLE": "No viable"
    }

    if estado_bd in estados_finales:
        return estados_finales[estado_bd]

    if not curso["id_instancia"]:
        return "Estado no disponible"

    # consultar las ejecuciones activas de flowable
    ejecuciones = obtener_actividades_activas(
        curso["id_instancia"]
    )

    actividades = {
        ejecucion["activityId"]
        for ejecucion in ejecuciones
        if ejecucion.get("activityId")
    }

    # etapa de preparacion
    if "Preparar" in actividades:
        return "En preparación"

    # etapa de elaboracion del informe
    if "Informe" in actividades or "EnviarInforme" in actividades:
        return "En elaboración del informe"

    # etapa de desarrollo
    if "Dictar" in actividades:
        return "En desarrollo"

    # curso confirmado, pero todavia sin comenzar
    if (
            "Confirmar" in actividades
            or "Activity_1018bdz" in actividades
            or "Fecha" in actividades
    ):
        return "Confirmado y pendiente de inicio"

    # no se pudo identificar la actividad actual
    return "Estado no disponible"