#!/usr/bin/env bash
# Ejecuta todo el proceso de minería:
# exporta el historial de Flowable a mineria/eventos.csv y lo analiza con PM4Py.
#
# Uso:
#   ./ejecutar_mineria.sh                  # pide usuario y contraseña de Flowable
#   ./ejecutar_mineria.sh usuario clave    # los toma de los parámetros

set -euo pipefail

# Pararse en proyecto-cursos (la carpeta donde está este script)
cd "$(dirname "$(readlink -f "$0")")"

PYTHON="$PWD/venv/bin/python"
FLOWABLE_URL="http://localhost:8080/flowable-ui/process-api"
FLOWABLE_USER="${1:-}"
FLOWABLE_PASS="${2:-}"

# Pedir lo que no se haya pasado por parámetro
if [[ -z "$FLOWABLE_USER" ]]; then
    read -r -p "Usuario de Flowable: " FLOWABLE_USER
fi
if [[ -z "$FLOWABLE_PASS" ]]; then
    read -r -s -p "Contraseña: " FLOWABLE_PASS
    echo ""
fi

if [[ ! -x "$PYTHON" ]]; then
    echo "Error: no se encontró el entorno virtual (venv)."
    exit 1
fi

if ! curl -fsS -o /dev/null -u "$FLOWABLE_USER:$FLOWABLE_PASS" \
        "$FLOWABLE_URL/repository/process-definitions"; then
    echo "Error: Flowable no responde en $FLOWABLE_URL (o las credenciales son incorrectas)."
    exit 1
fi

cd mineria

echo ">> Exportando el historial de Flowable..."
# Las credenciales se pasan por variables de entorno para que
# exportar_history.py no las vuelva a pedir.
FLOWABLE_USER="$FLOWABLE_USER" FLOWABLE_PASS="$FLOWABLE_PASS" \
    "$PYTHON" exportar_history.py

echo ""
echo ">> Analizando con PM4Py..."
"$PYTHON" analizar.py

echo ""
echo ">> Listo. Resultados en mineria/: eventos.csv y recorridos.png"