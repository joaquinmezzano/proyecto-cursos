import csv
from datetime import datetime
from getpass import getpass

import requests


# Configuración
BASE_URL = "http://localhost:8080/flowable-ui/process-api"

# ID del elemento <process id="..."> del BPMN.
PROCESS_KEY = "Process_Curso"

# IDs BPMN de las actividades y eventos de la etapa de negociación (etapa previa a la preparación del curso).
ACTIVIDADES = {
    "Activity_1xw400l",  # Evaluar Viabilidad
    "Activity_0iibzwu",  # Notificar Decisión (solicitud no viable)
    "Propuesta",         # Registrar y Elaborar propuesta
    "Enviar",            # Enviar propuesta
    "Modificar",         # Modificaciones (mensaje de la empresa)
    "Revisar",           # Revisar propuesta
    "Plazo",             # 5 días (temporizador)
    "Recordatorio",      # Enviar recordatorio
    "Rechazar",          # Rechazo (mensaje de la empresa)
    "Archivar",          # Archivar solicitud
    "Aceptar",           # Aceptación (mensaje de la empresa)
    "Activity_1eg7zcl",  # Habilitar acceso de la empresa
}

ARCHIVO_SALIDA = "eventos.csv"


def consultar_todos(session, recurso, filtros):
    """Recupera todas las páginas de una consulta REST."""
    inicio = 0

    while True:
        respuesta = session.get(
            f"{BASE_URL}/{recurso}",
            params={
                **filtros,
                "start": inicio,
                "size": 100,
            },
            timeout=30,
        )
        respuesta.raise_for_status()
        pagina = respuesta.json()
        registros = pagina["data"]

        if not registros:
            break

        yield from registros
        inicio += len(registros)

        if inicio >= pagina["total"]:
            break


def fecha_iso(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def main():
    usuario = input("Usuario de Flowable: ")
    clave = getpass("Contraseña: ")

    eventos = []

    with requests.Session() as session:
        session.auth = (usuario, clave)

        # Se incluyen también las instancias en curso: un curso que está en preparación o en dictado ya completó su negociación.
        instancias = consultar_todos(
            session,
            "history/historic-process-instances",
            {},
        )

        for instancia in instancias:
            definicion = instancia["processDefinitionId"]
            if not definicion.startswith(f"{PROCESS_KEY}:"):
                continue

            # Excluir instancias eliminadas o canceladas administrativamente.
            if instancia.get("deleteReason"):
                continue

            actividades = consultar_todos(
                session,
                "history/historic-activity-instances",
                {"processInstanceId": instancia["id"]},
            )

            for actividad in actividades:
                if actividad["activityId"] not in ACTIVIDADES:
                    continue

                # No exportar elementos pendientes.
                if not actividad.get("endTime"):
                    continue

                eventos.append({
                    "instancia": instancia["id"],
                    "definicion": definicion,
                    "evento_id": actividad["id"],
                    "actividad_id": actividad["activityId"],
                    "actividad": (
                        actividad.get("activityName")
                        or actividad["activityId"]
                    ),
                    "tipo": actividad["activityType"],
                    "inicio": actividad["startTime"],
                    "fecha_hora": actividad["endTime"],
                    "recurso": actividad.get("assignee") or "",
                })

    # Ordenar por instancia y fecha de finalización. El ID da un orden estable si coinciden las marcas temporales.
    eventos.sort(
        key=lambda evento: (
            evento["instancia"],
            fecha_iso(evento["fecha_hora"]),
            fecha_iso(evento["inicio"]),
            evento["evento_id"],
        )
    )

    columnas = [
        "instancia", "definicion", "evento_id",
        "actividad_id", "actividad", "tipo",
        "inicio", "fecha_hora", "recurso",
    ]

    with open(
        ARCHIVO_SALIDA, "w", newline="", encoding="utf-8"
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(eventos)

    cantidad_instancias = len({
        evento["instancia"] for evento in eventos
    })

    print(
        f"Generado {ARCHIVO_SALIDA}: "
        f"{len(eventos)} eventos de {cantidad_instancias} instancias."
    )


if __name__ == "__main__":
    main()
