#!/usr/bin/env bash
# Compila flowable-scripts, copia el JAR al contenedor de Flowable y lo reinicia.
#
# Uso:
#   ./script.sh                  # usa el contenedor "flowable-ui"
#   ./script.sh otro-contenedor  # p. ej. ./script.sh flowable-persistente

set -euo pipefail

CONTENEDOR="${1:-flowable-ui}"
JAR_ORIGEN="flowable-scripts/target/flowable-scripts-1.0-SNAPSHOT.jar"
JAR_DESTINO="/app/WEB-INF/lib/flowable-scripts.jar"

# Pararse en proyecto-cursos (la carpeta donde está este script), se ejecute desde donde se ejecute
cd "$(dirname "$(readlink -f "$0")")"

echo ">> Compilando flowable-scripts..."
(cd flowable-scripts && mvn clean package)

echo ">> Copiando el JAR a $CONTENEDOR..."
docker cp "$JAR_ORIGEN" "$CONTENEDOR:$JAR_DESTINO"

echo ">> Reiniciando $CONTENEDOR..."
docker restart "$CONTENEDOR"

echo ">> Listo. Para ver los logs: docker logs -f --tail 100 $CONTENEDOR"
