
#!/bin/bash

set -e

# Directorio raíz del proyecto
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Python del entorno virtual
PYTHON="$PROJECT_DIR/venv/bin/python"

# Aplicaciones
WEBSITE="$PROJECT_DIR/website/company_learning.py"
SIMULATOR="$PROJECT_DIR/business-simulator/business_app.py"
POM_JAVA="$PROJECT_DIR/flowable-scripts/pom.xml"

# Verificar entorno virtual
if [[ ! -x "$PYTHON" ]]; then
    echo "Error: no se encontró el entorno virtual."
    exit 1
fi

# Verificar aplicaciones
for app in "$WEBSITE" "$SIMULATOR" "$POM_JAVA"; do
    if [[ ! -f "$app" ]]; then
        echo "Error: no se encontró $app"
        exit 1
    fi
done

echo "Compilando aplicación Java (app_materiales.AppMateriales)..."
mvn -f "$POM_JAVA" compile -q

echo "Iniciando aplicaciones..."

# Iniciar Website
"$PYTHON" -m streamlit run "$WEBSITE" \
    --server.port 8501 &
WEBSITE_PID=$!

# Iniciar Business Simulator
"$PYTHON" -m streamlit run "$SIMULATOR" \
    --server.port 8502 &
SIMULATOR_PID=$!

# Iniciar AppMateriales (Java Swing / Flowable Java API)
mvn -f "$POM_JAVA" exec:java -Dexec.mainClass="app_materiales.AppMateriales" -q &
JAVA_APP_PID=$!

echo ""
echo "Website:            http://localhost:8501"
echo "Business Simulator: http://localhost:8502"
echo "App Materiales:     Ventana de escritorio Java abierta"
echo ""
echo "Presioná Ctrl+C para detener todas aplicaciones."

# Detener ambos procesos al salir
cleanup() {
    echo ""
    echo "Deteniendo aplicaciones..."

    kill "$WEBSITE_PID" "$SIMULATOR_PID" "$JAVA_APP_PID" 2>/dev/null || true
    pkill -f "app_materiales.AppMateriales" 2>/dev/null || true

    wait "$WEBSITE_PID" "$SIMULATOR_PID" "$JAVA_APP_PID" 2>/dev/null || true

    echo "Aplicaciones detenidas."
}

trap cleanup SIGINT SIGTERM

# Esperar a que terminen los procesos
wait
