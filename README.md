# proyecto-cursos

## Listener `CursosActivos` (regla de viabilidad)

### Qué hace

Implementa el punto **3.1 Regla de Negocio: Viabilidad**. Es un *Execution Listener*
asociado al evento `start` de la decision task **Evaluar Viabilidad**. Antes de que se
ejecute la tabla de decisión:

1. Consulta al motor las instancias de `Process_Curso` que todavía no finalizaron.
   La búsqueda es por *key*, así que incluye las instancias de **todas las versiones
   desplegadas**.
2. Excluye del conteo la instancia que está evaluando su propia viabilidad.
3. Guarda el resultado en la variable **`cantidadInstancias`**.

La tabla DMN `evaluarViabilidad` lee esa variable y devuelve `esViable`:
`true` si hay menos de 5 cursos activos y `false` si hay 5 o más.

> **Nota:** en una primera versión, esta lógica se implementó con un script Groovy
> (clase `ScriptExecutionListener` de Flowable con los campos `language` y `script`).
> Se reemplazó por esta clase Java para tener el código versionado, compilado y más
> fácil de mantener. La lógica es la misma.

### 1. Generar el JAR

Desde la carpeta `flowable-scripts/`:

```bash
mvn clean package
```

En IntelliJ: panel **Maven** → `flowable-scripts` → **Lifecycle** → doble clic en `package`.

El resultado queda en `flowable-scripts/target/flowable-scripts-1.0-SNAPSHOT.jar`.

### 2. Copiar el JAR al contenedor de Flowable

Ver el nombre del contenedor:

```bash
docker ps
```

Copiar el JAR (reemplazar `<contenedor>` por el nombre obtenido):

```bash
docker cp flowable-scripts/target/flowable-scripts-1.0-SNAPSHOT.jar \
  <contenedor>:/app/WEB-INF/lib/flowable-scripts.jar
```

Se copia siempre con el mismo nombre de destino (`flowable-scripts.jar`), así cada
versión nueva reemplaza a la anterior.

### 3. Reiniciar el contenedor

```bash
docker restart <contenedor>
```

Verificar que Flowable arrancó correctamente (opcional):

```bash
docker logs -f --tail 100 <contenedor>
```

Salir con `Ctrl+C` (no detiene el contenedor).

### 4. Configurar el listener en el modelo

En el editor de Flowable, seleccionar la tarea **Evaluar Viabilidad** →
**Execution listeners** y dejar un único listener con:

| Propiedad | Valor |
|-----------|-------|
| Event     | `start` |
| Class     | `listeners.CursosActivos` |
| Fields    | *(ninguno)* |

> Si se viene de la versión con Groovy, hay que **cambiar la clase**
> `org.flowable.engine.impl.bpmn.listener.ScriptExecutionListener` por
> `listeners.CursosActivos` y **borrar los campos `language` y `script`**. Si quedan,
> Flowable intenta inyectarlos en la clase Java y falla.

Guardar el modelo y **volver a publicar la app**.

### 5. Probar

1. Iniciar una instancia del proceso. Con menos de 5 instancias activas, debe crearse la
   tarea **Registrar y Elaborar propuesta** (asignada a `jefeAdministrativo`).
2. Con 5 o más instancias activas, la nueva instancia debe ir por **Notificar Decisión**
   y finalizar.
3. En los logs del contenedor (`docker logs -f <contenedor>`) se puede seguir la
   ejecución del listener.
