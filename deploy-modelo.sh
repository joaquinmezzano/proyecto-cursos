#!/usr/bin/env bash
# para dar permiso de ejecucion:
# chmod +x ./desplegar_modelo.sh

cd "$(dirname "$0")"

curl -fsS -o /dev/null -u admin:test \
  -F "file=@models/Institucion_de_capacitacion.bpmn20.xml" \
  http://localhost:8080/flowable-ui/process-api/repository/deployments \
  && echo "Modelo desplegado" \
  || echo "No se pudo desplegar el modelo"