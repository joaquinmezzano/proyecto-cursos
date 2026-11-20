#!/usr/bin/env bash
# Compila flowable-scripts, copia el JAR al contenedor de Flowable y lo reinicia.
#
# Uso:
#   ./deploy-flowable.sh                  # usa el contenedor "flowable-persistente"
#   ./deploy-flowable.sh otro-contenedor  # p. ej. ./deploy-flowable.sh flowable-ui

set -euo pipefail

CONTENEDOR="${1:-flowable-persistente}"
JAR_ORIGEN="flowable-scripts/target/flowable-scripts-1.0-SNAPSHOT.jar"
JAR_DESTINO="/app/WEB-INF/lib/flowable-scripts.jar"

# openpdf para siempre xq sino se reestablece
OPENPDF_ORIGEN=$(find ~/.m2/repository/com/github/librepdf/openpdf -name "openpdf-*.jar" ! -name "*sources*" ! -name "*javadoc*" | head -n 1)

# Pararse en proyecto-cursos (la carpeta donde está este script), se ejecute desde donde se ejecute
cd "$(dirname "$(readlink -f "$0")")"

echo ">> Compilando flowable-scripts..."
(cd flowable-scripts && mvn clean package)

echo ">> Copiando el JAR a $CONTENEDOR..."
docker cp "$JAR_ORIGEN" "$CONTENEDOR:$JAR_DESTINO"

if [ -n "$OPENPDF_ORIGEN" ]; then
    docker cp "$OPENPDF_ORIGEN" "$CONTENEDOR:/app/WEB-INF/lib/"
    echo "   - OpenPDF copiado: $(basename "$OPENPDF_ORIGEN")"
else
    echo "   ! Advertencia: No se encontró openpdf en ~/.m2"
fi

echo ">> Reiniciando $CONTENEDOR..."
docker restart "$CONTENEDOR"

echo ">> Listo. Para ver los logs: docker logs -f --tail 100 $CONTENEDOR"
