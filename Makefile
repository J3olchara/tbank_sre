APP := services/taskboard
COMPOSE := docker compose $(if $(wildcard $(APP)/.env),--env-file $(APP)/.env,) -f $(APP)/compose.yaml
GO_CACHE := /tmp/tbank-sre-go-cache
.PHONY: update check test frontend up down logs migrate archive integration
update:
	cd $(APP) && GOCACHE=$(GO_CACHE) go mod tidy
	cd $(APP) && gofmt -w cmd internal integration
check:
	cd $(APP) && test -z "$$(gofmt -l cmd internal integration)"
	cd $(APP) && GOCACHE=$(GO_CACHE) go vet ./...
	$(MAKE) test frontend grafana-json-check
test:
	cd $(APP) && GOCACHE=$(GO_CACHE) go test -race ./...
frontend:
	cd $(APP)/web && npm ci --no-audit --no-fund && npm run build
up:
	$(COMPOSE) up -d --build --wait
down:
	$(COMPOSE) down
logs:
	$(COMPOSE) logs -f web
migrate:
	$(COMPOSE) run --rm migrate
integration:
	cd $(APP) && TASKBOARD_URL=$${TASKBOARD_URL:-http://127.0.0.1:8080} GOCACHE=$(GO_CACHE) go test -tags=integration ./integration -count=1
archive:
	python3 scripts/package_hw01.py

.PHONY: k8s-start k8s-build k8s-deploy k8s-status k8s-scale k8s-forward k8s-validate archive-hw02
k8s-start:
	bash scripts/k8s.sh start
k8s-build:
	bash scripts/k8s.sh build
k8s-deploy:
	bash scripts/k8s.sh deploy
k8s-status:
	bash scripts/k8s.sh status
k8s-scale:
	bash scripts/k8s.sh scale $(or $(REPLICAS),3)
k8s-forward:
	bash scripts/k8s.sh forward
k8s-validate:
	bash scripts/k8s.sh validate
archive-hw02:
	python3 scripts/package_hw02.py

.PHONY: monitoring-install monitoring-status monitoring-forward monitoring-check monitoring-render archive-hw04
monitoring-install:
	bash scripts/monitoring.sh install
monitoring-status:
	bash scripts/monitoring.sh status
monitoring-forward:
	bash scripts/monitoring.sh forward
monitoring-check:
	python3 scripts/check_monitoring.py
monitoring-render:
	bash scripts/monitoring.sh render
archive-hw04:
	python3 scripts/package_hw04.py

.PHONY: logging-install logging-status logging-forward logging-validate logging-render logging-check archive-hw03
logging-install:
	bash scripts/logging.sh install
logging-status:
	bash scripts/logging.sh status
logging-forward:
	bash scripts/logging.sh forward
logging-validate:
	bash scripts/logging.sh validate
logging-render:
	bash scripts/logging.sh render
logging-check:
	python3 scripts/check_logs.py --generate
archive-hw03:
	python3 scripts/package_hw03.py

.PHONY: slo-install slo-render slo-validate slo-mode slo-load-start slo-load-stop slo-status slo-check archive-hw05
slo-install:
	bash scripts/slo.sh install
slo-render:
	bash scripts/slo.sh render
slo-validate:
	bash scripts/slo.sh validate
slo-mode:
	bash scripts/slo.sh mode $(or $(MODE),healthy)
slo-load-start:
	bash scripts/slo.sh load-start
slo-load-stop:
	bash scripts/slo.sh load-stop
slo-status:
	bash scripts/slo.sh status
slo-check:
	python3 scripts/check_slo.py
archive-hw05:
	python3 scripts/package_hw05.py

.PHONY: grafana-install grafana-status grafana-forward grafana-validate grafana-render grafana-import-postgres grafana-check grafana-export grafana-json-check grafana-record archive-hw06
grafana-install:
	bash scripts/grafana.sh install
grafana-status:
	bash scripts/grafana.sh status
grafana-forward:
	bash scripts/grafana.sh forward
grafana-validate:
	bash scripts/grafana.sh validate
grafana-render:
	bash scripts/grafana.sh render
grafana-import-postgres:
	bash scripts/grafana.sh import-postgres
grafana-check:
	bash scripts/grafana.sh check
grafana-export:
	bash scripts/grafana.sh export
grafana-json-check:
	python3 scripts/grafana_api.py validate
grafana-record:
	python3 scripts/record_hw06.py
archive-hw06:
	python3 scripts/package_hw06.py
