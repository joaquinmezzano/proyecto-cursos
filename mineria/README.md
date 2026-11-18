# Minería de procesos (actividad 4.4)

Análisis de la etapa de negociación de `Process_Curso` con PM4Py.

## Requisitos

- Flowable levantado en `localhost:8080`, con el proceso publicado.
- Entorno virtual del proyecto con `requirements.txt` instalado.
- Graphviz (`sudo apt install graphviz`).

## Ejecución

Desde la carpeta principal del proyecto:

```bash
source venv/bin/activate
cd mineria
python exportar_history.py   # usuario: admin, contraseña: test
python analizar.py
```

1. `exportar_history.py` lee el historial de Flowable y genera `eventos.csv` con las actividades de negociación que ocurrieron.
2. `analizar.py` muestra los tres recorridos más frecuentes y genera `recorridos.png`, el grafo de sucesión directa (cada flecha indica cuántas veces una actividad siguió a otra).

## Resultados

17 instancias, 7 recorridos diferentes. Los tres más frecuentes:

| Casos | % | Recorrido |
|---|---|---|
| 7 | 41,2 % | Evaluar Viabilidad → Registrar y Elaborar propuesta → Enviar propuesta → Aceptación → Habilitar acceso de la empresa |
| 4 | 23,5 % | Evaluar Viabilidad → Registrar y Elaborar propuesta → Enviar propuesta → Rechazo → Archivar solicitud |
| 2 | 11,8 % | Evaluar Viabilidad → Registrar y Elaborar propuesta → Enviar propuesta → 5 días → Enviar recordatorio → 5 días → Enviar recordatorio → 5 días → Archivar solicitud |

Los otros cuatro tienen un caso cada uno: modificación y rechazo, modificación y aceptación, recordatorio y aceptación, y solicitud no viable.

## Conclusión

**Coincidencias:** Todos los caminos de la negociación del BPMN aparecen en los datos: solicitud no viable, aceptación, rechazo, modificaciones (ciclo Revisar → Enviar propuesta) y falta de respuesta. No se observó ningún recorrido que el modelo no permita. Las instancias sin respuesta archivan la solicitud después de dos recordatorios.

**Diferencias:** El grafo solo muestra actividades y el orden en que ocurrieron, no los gateways ni sus condiciones. Las decisiones del BPMN ("¿Es viable?", "Esperar respuesta" y el límite de 2 recordatorios) aparecen solo como bifurcaciones y ciclos, y su lógica no se puede leer en el grafo. Además, el temporizador "5 días" figura como una actividad más.

**Limitaciones:**
- La muestra es chica (17 instancias) y casi toda es generada para pruebas: 13 instancias se crearon por la API de Flowable, igual que la web y el simulador.
- El temporizador de 5 días se adelantó manualmente, así que los tiempos no son reales. El análisis sirve para los recorridos, no para las duraciones.
- Se excluyeron 11 instancias canceladas o borradas por un administrador.
- Flowable registra como finalizados los eventos del gateway que no se dispararon. Se descartan si no se tomó ningún flujo que salga de ellos.
