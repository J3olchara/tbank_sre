#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TOOLS_DIR=${TOOLS_DIR:-$ROOT/.tools/bin}
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo "This installer supports Linux amd64; use the official instructions for your platform" >&2
  exit 1
fi
mkdir -p "$TOOLS_DIR"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl --fail --location --silent --show-error https://github.com/kubernetes/minikube/releases/download/v1.39.0/minikube-linux-amd64 -o "$work/minikube"
curl --fail --location --silent --show-error https://github.com/kubernetes/minikube/releases/download/v1.39.0/minikube-linux-amd64.sha256 -o "$work/minikube.sha256"
curl --fail --location --silent --show-error https://dl.k8s.io/release/v1.35.0/bin/linux/amd64/kubectl -o "$work/kubectl"
curl --fail --location --silent --show-error https://dl.k8s.io/release/v1.35.0/bin/linux/amd64/kubectl.sha256 -o "$work/kubectl.sha256"
python3 - "$work" <<'PY'
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1])
for name in ['minikube', 'kubectl']:
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    expected = (root / (name + '.sha256')).read_text().split()[0]
    if actual != expected:
        raise SystemExit(name + ': checksum mismatch')
    print(name + ': checksum verified')
PY
install -m 0755 "$work/minikube" "$work/kubectl" "$TOOLS_DIR/"
printf 'Tools installed in %s. Add this directory to PATH.\n' "$TOOLS_DIR"
