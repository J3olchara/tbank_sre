#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PROFILE=${PROFILE:-tbank-sre-hw02}
NAMESPACE=taskboard-lab
IMAGE=tbank-sre-taskboard:hw02
MANIFESTS=deploy/k8s
k() { kubectl --context "$PROFILE" --namespace "$NAMESPACE" "$@"; }

secret() {
  # Preserve credentials across redeployments: the PostgreSQL PVC outlives pods.
  local credentials=homework/02/.env
  if [[ ! -f "$credentials" ]]; then
    umask 077
    python3 -c 'import secrets; print("POSTGRES_PASSWORD="+secrets.token_hex(24))' > "$credentials"
  fi
  python3 - "$credentials" "$MANIFESTS/secret.template.yaml" <<'PYCODE' | k apply -f -
from pathlib import Path
import re, sys
value = Path(sys.argv[1]).read_text().strip().removeprefix("POSTGRES_PASSWORD=")
if not re.fullmatch(r"[a-zA-Z0-9_-]{16,128}", value):
    raise SystemExit("Local POSTGRES_PASSWORD must be 16-128 URL-safe characters")
print(Path(sys.argv[2]).read_text().replace("${POSTGRES_PASSWORD}", value))
PYCODE
}

case "${1:-}" in
  start)
    minikube start -p "$PROFILE" --driver=docker --container-runtime=docker \
      --kubernetes-version=v1.35.0 --cpus=2 --memory=3072
    ;;
  build)
    archive=$(mktemp --suffix=.tar)
    trap 'rm -f "$archive"' EXIT
    # Subshell prevents the minikube Docker endpoint leaking into later commands.
    (
      eval "$(minikube -p "$PROFILE" docker-env)"
      docker build -t "$IMAGE" services/taskboard
      docker save -o "$archive" "$IMAGE"
    )
    # Loading the archive works even when host and node use different daemons.
    minikube -p "$PROFILE" image load "$archive"
    ;;
  secret)
    secret
    ;;
  deploy)
    k apply -f "$MANIFESTS/namespace.yaml"
    k apply -f "$MANIFESTS/configmap.yaml"
    secret
    k apply -f "$MANIFESTS/postgres.yaml"
    k rollout status statefulset/postgres --timeout=180s
    # A completed Job is retained as evidence. Re-run migrations on the next release.
    k delete job taskboard-migrate --ignore-not-found --wait=true
    k apply -f "$MANIFESTS/migrate.yaml"
    k wait --for=condition=complete job/taskboard-migrate --timeout=180s
    k apply -f "$MANIFESTS/app.yaml"
    k rollout status deployment/taskboard --timeout=180s
    ;;
  status)
    k get pods,deploy,statefulset,svc,pvc,job
    ;;
  scale)
    replicas=${2:-3}
    [[ "$replicas" =~ ^[1-9][0-9]*$ ]] || { echo "Replicas must be a positive integer" >&2; exit 1; }
    k scale deployment/taskboard --replicas="$replicas"
    k rollout status deployment/taskboard --timeout=180s
    k get pods -o wide
    ;;
  forward)
    k port-forward service/taskboard "${APP_PORT:-18080}:8080" --address=127.0.0.1
    ;;
  validate)
    for manifest in namespace configmap postgres migrate app; do
      k apply --dry-run=server -f "$MANIFESTS/$manifest.yaml"
    done
    ;;
  *) echo "Usage: $0 {start|build|secret|deploy|status|scale [N]|forward|validate}" >&2; exit 1 ;;
esac
