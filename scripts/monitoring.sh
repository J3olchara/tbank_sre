#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PROFILE=${PROFILE:-tbank-sre-hw02}
CHART_VERSION=0.49.0
RELEASE=vm-single
HELM_DIR=${HELM_DIR:-$ROOT/.tools/helm}
export HELM_REPOSITORY_CONFIG="$HELM_DIR/repositories.yaml"
export HELM_REPOSITORY_CACHE="$HELM_DIR/cache"
mkdir -p "$HELM_REPOSITORY_CACHE"
k() { kubectl --context "$PROFILE" -n monitoring "$@"; }
case "${1:-}" in
  install)
    kubectl --context "$PROFILE" -n taskboard-lab apply -f deploy/monitoring/rbac.yaml
    helm repo add vm https://victoriametrics.github.io/helm-charts --force-update
    helm repo update vm
    helm upgrade --install "$RELEASE" vm/victoria-metrics-single \
      --version "$CHART_VERSION" --kube-context "$PROFILE" \
      --namespace monitoring --create-namespace -f deploy/monitoring/values.yaml \
      --wait --timeout 5m
    ;;
  status)
    helm list --kube-context "$PROFILE" --namespace monitoring
    k get pods,svc,pvc
    ;;
  forward)
    k port-forward service/vm-single "${VM_PORT:-8428}:8428" --address=127.0.0.1
    ;;
  render)
    mkdir -p artifacts/hw04
    helm repo add vm https://victoriametrics.github.io/helm-charts --force-update
    helm template "$RELEASE" vm/victoria-metrics-single --version "$CHART_VERSION" \
      --namespace monitoring -f deploy/monitoring/values.yaml > artifacts/hw04/victoriametrics-rendered.yaml
    ;;
  *) echo "Usage: $0 {install|status|forward|render}" >&2; exit 1 ;;
esac
