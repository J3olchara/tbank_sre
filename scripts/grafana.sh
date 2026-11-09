#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PROFILE=${PROFILE:-tbank-sre-hw02}
CHART_VERSION=14.4.0
export HELM_REPOSITORY_CONFIG="$ROOT/.tools/helm/repositories.yaml"
export HELM_REPOSITORY_CACHE="$ROOT/.tools/helm/cache"
mkdir -p "$HELM_REPOSITORY_CACHE" artifacts/hw06
k() { kubectl --context "$PROFILE" -n monitoring "$@"; }
configmap() {
  k create configmap grafana-taskboard-dashboard \
    --from-file=taskboard.json=deploy/grafana/dashboards/taskboard.json --dry-run=client -o yaml
}
secret() {
  if k get secret grafana-admin >/dev/null 2>&1; then return; fi
  if [[ ! -f homework/06/.env ]]; then
    umask 077
    python3 -c 'import secrets; print("GRAFANA_ADMIN_PASSWORD="+secrets.token_hex(24))' > homework/06/.env
  fi
  python3 - <<'PY' | k apply -f -
from pathlib import Path
import re
value=Path('homework/06/.env').read_text().strip().removeprefix('GRAFANA_ADMIN_PASSWORD=')
if not re.fullmatch(r'[a-zA-Z0-9_-]{16,128}',value):
    raise SystemExit('GRAFANA_ADMIN_PASSWORD must be 16-128 URL-safe characters')
print(Path('deploy/grafana/secret.template.yaml').read_text().replace('${GRAFANA_ADMIN_PASSWORD}',value))
PY
}
case "${1:-}" in
  install|render)
    python3 scripts/grafana_api.py validate
    helm repo add grafana-community https://grafana-community.github.io/helm-charts --force-update
    if [[ "$1" == install ]]; then
      kubectl --context "$PROFILE" create namespace monitoring --dry-run=client -o yaml | kubectl --context "$PROFILE" apply -f -
      secret
      configmap | k apply -f -
      helm upgrade --install grafana grafana-community/grafana --version "$CHART_VERSION" \
        --kube-context "$PROFILE" --namespace monitoring -f deploy/grafana/values.yaml --wait --timeout 5m
      # The dashboard is in an external ConfigMap, outside Helm's checksum.
      k rollout restart deployment/grafana
      k rollout status deployment/grafana --timeout=180s
    else
      helm template grafana grafana-community/grafana --version "$CHART_VERSION" \
        --namespace monitoring -f deploy/grafana/values.yaml > artifacts/hw06/grafana-rendered.yaml
      configmap > artifacts/hw06/dashboard-configmap.yaml
    fi
    ;;
  validate)
    python3 scripts/grafana_api.py validate
    configmap | k apply --dry-run=server -f -
    helm template grafana grafana-community/grafana --version "$CHART_VERSION" \
      --namespace monitoring -f deploy/grafana/values.yaml | k apply --dry-run=server -f -
    ;;
  status)
    helm list --kube-context "$PROFILE" -n monitoring
    k get pods,svc,pvc
    ;;
  forward) k port-forward svc/grafana "${GRAFANA_PORT:-3000}:80" --address=127.0.0.1 ;;
  import-postgres|check|export) python3 scripts/grafana_api.py "$1" ;;
  *) echo "Usage: $0 {install|render|validate|status|forward|import-postgres|check|export}" >&2; exit 1 ;;
esac
