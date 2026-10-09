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
