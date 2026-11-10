"""Package alert configs, sources, real screenshots and delivery verification."""
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

from check_alerting import EXPECTED, NAMES

root = Path(__file__).resolve().parents[1]
proof_dir = root / 'artifacts/hw06'
verification = json.loads((proof_dir / 'verification.json').read_text())
if verification['phases'] != ['healthy', 'slow', 'errors', 'runtime', 'recovery']:
    raise SystemExit('Missing verified alert phases')
if not all(verification.get(k) for k in ['screenshots', 'healthy_restored', 'load_job_deleted']):
    raise SystemExit('Missing real screenshots or cleanup verification')
for phase, required in EXPECTED.items():
    proof = json.loads((proof_dir / (phase + '.json')).read_text())
    delivered = {a['labels']['alertname'] for d in proof['notifications'] for a in d['payload']['alerts'] if a['status'] == 'firing'}
    if not required <= delivered or any(proof['states'][name] != 'firing' for name in required):
        raise SystemExit('Missing firing rule or delivered webhook: ' + phase)
recovery = json.loads((proof_dir / 'recovery.json').read_text())
resolved = {a['labels']['alertname'] for d in recovery['notifications'] for a in d['payload']['alerts'] if a['status'] == 'resolved'}
if not NAMES <= resolved or any(v != 'inactive' for v in recovery['states'].values()):
    raise SystemExit('Missing resolved webhook or healthy recovery')
report = root / 'homework/06/Отчёт.md'
for relative in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', report.read_text()):
    path = report.parent / relative
    if not path.is_file() or path.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('Missing real screenshot: ' + relative)
rendered = proof_dir / 'configmaps-rendered.yaml'
if not rendered.is_file():
    raise SystemExit('Run make alerting-render')

files = {}
excluded = {'node_modules', 'dist', '.venv', '__pycache__', '.git'}
for folder in ['services/taskboard', 'deploy', 'homework/06']:
    for path in sorted((root / folder).rglob('*')):
        if path.is_file() and not set(path.parts) & excluded and path.name != '.env':
            files[str(path.relative_to(root))] = path
for path in sorted((root / 'scripts').glob('*')):
    if path.is_file():
        files['scripts/' + path.name] = path
for name in ['Makefile', 'homework/02/.env.example']:
    files[name] = root / name
files['README.md'] = root / 'homework/06/README.md'
for path in sorted(proof_dir.glob('*.json')):
    files['verification/' + path.name] = path
files['deploy/alerting/configmaps-rendered.yaml'] = rendered
for path in sorted((report.parent / 'screenshots').glob('*.png')):
    files['screenshots/' + path.name] = path
output = root / 'artifacts/homework-06.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name, path in sorted(files.items()):
        archive.write(path, name)
    archive.writestr('Отчёт.md', report.read_text().replace('../../deploy/', 'deploy/'))
print(f'{output} ({len(NAMES)} verified firing/resolved alerts, real UI screenshots)')
