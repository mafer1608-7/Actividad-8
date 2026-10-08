#!/usr/bin/env bash
# Sube las imágenes a Docker Hub. Requiere: docker login  y  .env con DOCKERHUB_USER
set -euo pipefail
source .env
TAG="${TAG:-latest}"
for img in lab-sim-base lab-router lab-admin lab-track-server lab-player lab-robot-sim; do
  echo ">> docker push ${DOCKERHUB_USER}/${img}:${TAG}"
  docker push "${DOCKERHUB_USER}/${img}:${TAG}"
done
echo "Listo. Pega estos nombres en el README (sección Docker Hub)."
