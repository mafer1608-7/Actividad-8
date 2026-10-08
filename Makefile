include .env
export
USER_HUB ?= $(DOCKERHUB_USER)
TAG ?= latest

.PHONY: base build up down logs test emulate analyze push clean

base:
	docker build -f docker/base/Dockerfile -t $(USER_HUB)/lab-sim-base:$(TAG) .

build: base
	docker compose build

up: build
	docker compose up -d
	@echo "Dashboard: http://localhost:8080"

down:
	docker compose down

logs:
	docker compose logs -f --tail=50

test:
	bash tests/test_isolation.sh

emulate:            # ESP32 virtuales (sin hardware): ver tools/esp32_emulator.py
	python3 tools/launch_emulators.py

analyze:
	python3 tools/analyze_metrics.py data/metrics.csv

push:
	bash scripts/push_images.sh

clean:
	docker compose down -v
