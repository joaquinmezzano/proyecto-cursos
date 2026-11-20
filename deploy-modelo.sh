#!/usr/bin/env bash
# Publica models/Institucion_de_capacitacion.bpmn20.xml en Flowable (crea una nueva version de Process_Curso).
# Requiere Flowable levantado en localhost:8080 y el JAR ya desplegado (./deploy-flowable.sh).
# para dar permiso de ejecucion:
# chmod +x ./deploy-modelo.sh

cd "$(dirname "$0")"

curl -fsS -o /dev/null -u admin:test \
  -F "file=@models/Institucion_de_capacitacion.bpmn20.xml" \
  http://localhost:8080/flowable-ui/process-api/repository/deployments \
  && echo "Modelo desplegado" \
  || echo "No se pudo desplegar el modelo"