#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PROFILE=${PROFILE:-tbank-sre-hw02}
HELM_DIR=${HELM_DIR:-$ROOT/.tools/helm}
export HELM_REPOSITORY_CONFIG="$HELM_DIR/repositories.yaml"
export HELM_REPOSITORY_CACHE="$HELM_DIR/cache"
mkdir -p "$HELM_REPOSITORY_CACHE"
k() { kubectl --context "$PROFILE" -n logging "$@"; }
case "${1:-}" in
  install)
    helm repo add vm https://victoriametrics.github.io/helm-charts --force-update
    helm upgrade --install victorialogs vm/victoria-logs-single \
      --version 0.13.11 --kube-context "$PROFILE" --namespace logging --create-namespace \
      -f deploy/logging/values.yaml --wait --timeout 5m
    k apply -f deploy/logging/vector-config.yaml -f deploy/logging/vector.yaml
    k rollout restart daemonset/vector-taskboard
    k rollout status daemonset/vector-taskboard --timeout=180s
    ;;
  status)
    helm list --kube-context "$PROFILE" --namespace logging
    k get pods,daemonset,svc,pvc
    ;;
  forward)
    exec kubectl --context "$PROFILE" -n logging port-forward service/victorialogs "${VL_PORT:-9428}:9428" --address=127.0.0.1
    ;;
  validate)
    k apply --dry-run=server -f deploy/logging/vector-config.yaml -f deploy/logging/vector.yaml
    ;;
  render)
    mkdir -p artifacts/hw03
    helm repo add vm https://victoriametrics.github.io/helm-charts --force-update
    helm template victorialogs vm/victoria-logs-single --version 0.13.11 \
      --namespace logging -f deploy/logging/values.yaml > artifacts/hw03/victorialogs-rendered.yaml
    ;;
  *) echo "Usage: $0 {install|status|forward|validate|render}" >&2; exit 1 ;;
esac
