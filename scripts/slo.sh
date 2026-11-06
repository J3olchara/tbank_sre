#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PROFILE=${PROFILE:-tbank-sre-hw02}
k() { kubectl --context "$PROFILE" -n taskboard-lab "$@"; }
case "${1:-}" in
  install|render)
    export HELM_REPOSITORY_CONFIG="$ROOT/.tools/helm/repositories.yaml"
    export HELM_REPOSITORY_CACHE="$ROOT/.tools/helm/cache"
    mkdir -p "$HELM_REPOSITORY_CACHE" artifacts/hw05
    helm repo add vm https://victoriametrics.github.io/helm-charts --force-update
    if [[ "$1" == install ]]; then
      helm upgrade --install vm-single vm/victoria-metrics-single --version 0.49.0 \
        --kube-context "$PROFILE" --namespace monitoring --create-namespace \
        -f deploy/monitoring/values.yaml -f deploy/slo/monitoring-values.yaml --wait --timeout 5m
      k apply -f deploy/slo/prober.yaml
      k rollout restart deployment/taskboard-prober
      k rollout status deployment/taskboard-prober --timeout=180s
    else
      helm template vm-single vm/victoria-metrics-single --version 0.49.0 --namespace monitoring \
        -f deploy/monitoring/values.yaml -f deploy/slo/monitoring-values.yaml > artifacts/hw05/victoriametrics-rendered.yaml
    fi
    ;;
  validate)
    k apply --dry-run=server -f deploy/slo/prober.yaml -f deploy/slo/load.yaml
    ;;
  mode)
    case "${2:-}" in
      healthy) delay=0s; failure=0 ;;
      slow) delay=750ms; failure=0 ;;
      errors) delay=0s; failure=1 ;;
      *) echo "Usage: $0 mode {healthy|slow|errors}" >&2; exit 1 ;;
    esac
    k set env deployment/taskboard "DEMO_LATENCY=$delay" "DEMO_FAILURE_EVERY=$failure"
    k rollout status deployment/taskboard --timeout=180s
    ;;
  load-start)
    k delete job taskboard-slo-load --ignore-not-found --wait=true
    k wait --for=delete pod -l job-name=taskboard-slo-load --timeout=60s
    k apply -f deploy/slo/load.yaml
    k wait --for=condition=Ready pod -l job-name=taskboard-slo-load --timeout=90s
    ;;
  load-stop) k delete job taskboard-slo-load --ignore-not-found --wait=true ;;
  status) k get pods -l 'app in (taskboard,taskboard-prober,taskboard-slo-load)' ;;
  *) echo "Usage: $0 {install|render|validate|mode|load-start|load-stop|status}" >&2; exit 1 ;;
esac
