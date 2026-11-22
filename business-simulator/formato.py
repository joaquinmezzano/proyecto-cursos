# Textos que se muestran en la interfaz


# "2026-11-22..." -> "22/11/2026"
def fecha_dd_mm_aaaa(fecha):
    return f"{fecha[8:10]}/{fecha[5:7]}/{fecha[0:4]}"


# Arma el texto que se ve en el selector para cada instancia
def etiqueta_instancia(instancia, datos_cursos):
    inicio = fecha_dd_mm_aaaa(instancia["startTime"][:10])
    datos = datos_cursos.get(instancia["id"])
    if datos:
        nombre_curso, nombre_empresa = datos
        return f"{nombre_curso} — {nombre_empresa} (iniciado el {inicio})"
    # Todavía no hay curso registrado en la base
    return f"Solicitud sin propuesta registrada (iniciada el {inicio}) · ID {instancia['id']}"


# Recordatorio de la institucion: la tarea "Enviar recordatorio" deja el numero y la fecha en variables del proceso.
def texto_recordatorio(variables):
    if variables is None:
        return None
    cantidad = variables.get("recordatorios") or 0
    if cantidad <= 0:
        return None
    fecha = str(variables.get("fechaUltimoRecordatorio") or "")[:16].replace("T", " ")
    texto = f"**Recordatorio {cantidad} de 2** de la institucion" + (f" (recibido el {fecha})" if fecha else "")
    texto += ": la propuesta sigue sin respuesta."
    if cantidad >= 2:
        texto += " Es el ultimo aviso: si no responde antes de que venza el plazo, la solicitud se archiva."
    else:
        texto += " Por favor acepte, rechace o pida modificaciones."
    return texto
