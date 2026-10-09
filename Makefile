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
	$(MAKE) test frontend
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
