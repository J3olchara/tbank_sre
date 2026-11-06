#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TOOLS_DIR=${TOOLS_DIR:-$ROOT/.tools/bin}
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo "This installer supports Linux amd64; use the official Helm instructions on other platforms" >&2
  exit 1
fi
mkdir -p "$TOOLS_DIR"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl --fail --location --silent --show-error https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz -o "$work/helm.tar.gz"
curl --fail --location --silent --show-error https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz.sha256sum -o "$work/helm.sha256"
python3 - "$work" "$TOOLS_DIR" <<'PY'
import hashlib
from pathlib import Path
import sys
import tarfile
root, target = map(Path, sys.argv[1:])
if hashlib.sha256((root / 'helm.tar.gz').read_bytes()).hexdigest() != (root / 'helm.sha256').read_text().split()[0]:
    raise SystemExit('Helm checksum mismatch')
with tarfile.open(root / 'helm.tar.gz') as archive:
    (target / 'helm').write_bytes(archive.extractfile('linux-amd64/helm').read())
(target / 'helm').chmod(0o755)
print('Helm 3.19.0: checksum verified')
PY
