# proyecto-cursos

Sistema de gestión de cursos de capacitación para empresas sobre **Flowable 6.8** (proceso `Process_Curso`).

| Componente | Carpeta | Qué es | Dónde corre |
|---|---|---|---|
| Web de la institución | `website/` | Streamlit: solicitud de cursos, login de empresas y personal, análisis de ejecuciones | http://localhost:8501 |
| Simulador de la empresa | `business-simulator/` | Streamlit: la empresa acepta, rechaza o pide cambios a la propuesta y envía la nómina | http://localhost:8502 |
| App Materiales | `flowable-scripts/.../app_materiales` | Ventana Java para la tarea "Preparar materiales" | Escritorio |
| Lógica del proceso | `flowable-scripts/` | Listeners y delegates | Contenedor Flowable |
| Modelo | `models/` | BPMN del proceso | Flowable |
| Base de datos | `bdd/institucion.sql` | Esquema de la base `institucion` (empresas, cursos, cuentas) | Postgres |
| Minería | `mineria/` | Exporta el historial de Flowable y lo analiza con PM4Py | Línea de comandos |

---

## 1. Instalación (una sola vez)

### 1.1 - Requisitos
- Docker con Docker Compose
- Python 3 con `venv`
- Java 17 (el proyecto compila para Java 11) y Maven
- Graphviz, solo para la minería (`sudo dnf install graphviz` o `sudo apt install graphviz`)

### 1.2 - Flowable y Postgres
Flowable y Postgres corren con Docker Compose. El `docker-compose.yml` **no está en este repositorio**, y tiene que cumplir con lo que espera el código:

| Servicio | Imagen | Nombre del contenedor | Puerto |
|---|---|---|---|
| Flowable | `flowable/flowable-ui:6.8.0` | `flowable-persistente` | `127.0.0.1:8080:8080` |
| Postgres | `postgres:15` | `flowable-postgres` (servicio `postgres`) | `127.0.0.1:5434:5432` |

- Usuario de Postgres `flowable`, base `flowable`. La contraseña tiene que ser la misma que figura en `website/servicios.py` (`DB_PASS`).
- Flowable se conecta a Postgres con `jdbc:postgresql://postgres:5432/flowable`, en la misma red de Docker.

```bash
cd <carpeta del docker-compose.yml>
docker compose up -d
```

### 1.3 - Entorno de Python
Desde la carpeta principal del proyecto:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 1.4 - Base de datos `institucion`
Va en el mismo Postgres que usa Flowable:
```bash
docker exec -i flowable-postgres psql -U flowable -d postgres -c "CREATE DATABASE institucion"
docker exec -i flowable-postgres psql -U flowable -d institucion < bdd/institucion.sql
```

### 1.5 - Usuarios y grupos en Flowable
Entrá a http://localhost:8080/flowable-ui con `admin` / `test`. En **Identity management**, creá:

| Grupo | Usuarios |
|---|---|
| `administracion` | `administrativo`, `jefeAdministrativo` |
| `docentes` | `docente1`, `docente2`, `jefeEquipoDocente` |

El personal entra a la web con estos usuarios y sus contraseñas de Flowable.

### 1.6 - Desplegar el código, el modelo y la tabla de decisión
```bash
chmod +x *.sh
./deploy-flowable.sh      # compila flowable-scripts, copia el JAR al contenedor y reinicia Flowable
# esperar a que Flowable termine de levantar (http://localhost:8080/flowable-ui responde)
./deploy-modelo.sh        # publica models/Institucion_de_capacitacion.bpmn20.xml
```
La tabla DMN `evaluarViabilidad` se publica aparte. Podés hacerlo desde el Modeler de Flowable, importando `models/decision_table_Evaluar_viabilidad.dmn` y publicando la app, o por REST:
```bash
curl -u admin:test -F "file=@models/decision_table_Evaluar_viabilidad.dmn" \
  http://localhost:8080/flowable-ui/dmn-api/dmn-repository/deployments
```

---

## 2. Puesta en marcha de cada sesión
1. Levantar los contenedores si no están corriendo: `docker compose up -d` en la carpeta del compose. Para verificarlo, usá `docker ps`; tienen que aparecer `flowable-persistente` y `flowable-postgres`.
2. Activar el entorno: `source venv/bin/activate`.
3. Elegir qué ejecutar (sección 3).

---

## 3. Qué ejecutar

### 3.A - Todo junto (recomendado)
Levanta la web, el simulador y App Materiales. Con `Ctrl+C` se detiene todo.
```bash
./start-web-and-app.sh
```
- Web: http://localhost:8501
- Simulador: http://localhost:8502
- App Materiales: se abre una ventana Java

### 3.B - Solo la web
```bash
cd website
streamlit run company_learning.py
```
Desde la pantalla de inicio podés:
- **Solicitar un curso**: no requiere cuenta. Crea la empresa y el curso en la base e inicia una instancia del proceso.
- **Iniciar sesión**:
  - Una empresa entra con los dígitos de su CUIT y la contraseña `empresa123`. La cuenta existe recién después de que la empresa acepta una propuesta.
  - El personal entra con su usuario y contraseña de Flowable.
- **Análisis de ejecuciones**: pide usuario y contraseña de Flowable.

### 3.C - Solo el simulador de la empresa
```bash
cd business-simulator
streamlit run business_app.py
```
Lista las instancias en curso y permite descargar la propuesta (PDF), aceptarla, rechazarla, pedir modificaciones y enviar la nómina de participantes.

### 3.D - Solo App Materiales
```bash
mvn -f flowable-scripts/pom.xml compile exec:java -Dexec.mainClass="app_materiales.AppMateriales"
```
Se conecta directamente a la base de Flowable (`localhost:5434`). Hay que entrar con un usuario del grupo `administracion`.

### 3.E - Minería de procesos
```bash
./ejecutar_mineria.sh                     # pide usuario y contraseña de Flowable
./ejecutar_mineria.sh <user> <password>
```
Genera `mineria/eventos.csv` y `mineria/recorridos.png`. Más detalles en [`mineria/README.md`](mineria/README.md).