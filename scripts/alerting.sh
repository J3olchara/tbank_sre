#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PROFILE=${PROFILE:-tbank-sre-hw02}
k() { kubectl --context "$PROFILE" -n monitoring "$@"; }
configmaps() {
  k create configmap taskboard-alert-rules --from-file=rules.yaml=deploy/alerting/rules.yaml --dry-run=client -o yaml
  echo '---'
  k create configmap taskboard-alertmanager --from-file=alertmanager.yml=deploy/alerting/alertmanager.yml --dry-run=client -o yaml
}
case "${1:-}" in
  install)
    configmaps | k apply -f -
    for name in inbox alertmanager vmalert; do
      k apply -f "deploy/alerting/$name.yaml"
    done
    for name in alert-inbox alertmanager vmalert; do
      k rollout restart deployment/"$name"
      k rollout status deployment/"$name" --timeout=180s
    done
    ;;
  validate)
    configmaps | k apply --dry-run=server -f -
    for name in inbox alertmanager vmalert; do
      k apply --dry-run=server -f "deploy/alerting/$name.yaml"
    done
    ;;
  test)
    docker run --rm --network none -v "$ROOT/deploy/alerting:/work:ro" \
      victoriametrics/vmalert:v1.154.0 -rule=/work/rules.yaml -dryRun
    docker run --rm --network none --entrypoint /bin/amtool -v "$ROOT/deploy/alerting:/work:ro" \
      prom/alertmanager:v0.35.0 check-config /work/alertmanager.yml
    docker run --rm --network none -v "$ROOT/deploy/alerting:/work:ro" --workdir /work \
      victoriametrics/vmalert-tool:v1.154.0 unittest --files=/work/rules.test.yaml
    ;;
  render)
    mkdir -p artifacts/hw06
    configmaps > artifacts/hw06/configmaps-rendered.yaml
    ;;
  mode)
    delay=0s; failure=0; goroutines=0; heap=0
    case "${2:-}" in
      healthy) ;;
      slow) delay=750ms ;;
      errors) failure=1 ;;
      runtime) goroutines=300; heap=48 ;;
      *) echo "Usage: $0 mode {healthy|slow|errors|runtime}" >&2; exit 1 ;;
    esac
    kubectl --context "$PROFILE" -n taskboard-lab set env deployment/taskboard \
      "DEMO_LATENCY=$delay" "DEMO_FAILURE_EVERY=$failure" \
      "DEMO_GOROUTINES=$goroutines" "DEMO_HEAP_MIB=$heap"
    kubectl --context "$PROFILE" -n taskboard-lab rollout status deployment/taskboard --timeout=180s
    ;;
  forward)
    children=()
    trap 'kill "${children[@]}" 2>/dev/null || true' EXIT
    k port-forward service/vmalert "${VMALERT_PORT:-18880}:8880" --address=127.0.0.1 & children+=("$!")
    k port-forward service/alertmanager "${ALERTMANAGER_PORT:-19093}:9093" --address=127.0.0.1 & children+=("$!")
    k port-forward service/alert-inbox "${ALERT_INBOX_PORT:-18085}:8085" --address=127.0.0.1 & children+=("$!")
    wait -n
    ;;
  status)
    k get pods -l 'app in (taskboard-vmalert,taskboard-alertmanager,taskboard-alert-inbox)'
    k get deployment/vmalert deployment/alertmanager deployment/alert-inbox \
      service/vmalert service/alertmanager service/alert-inbox \
      pvc/alertmanager-data pvc/alert-inbox-data
    ;;
  *) echo "Usage: $0 {install|validate|test|render|mode|forward|status}" >&2; exit 1 ;;
esac
