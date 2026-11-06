"""Package logging sources, exact Helm render, report and 4 actual vmui screenshots."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
queries = json.loads((root / 'homework/03/queries.json').read_text())
proof = root / 'artifacts/hw03/vmui-queries.json'
rendered = root / 'artifacts/hw03/victorialogs-rendered.yaml'
if not proof.is_file() or not rendered.is_file():
    raise SystemExit('Run make logging-render and scripts/capture_logs_vmui.cjs first')
evidence = {item['id']: item for item in json.loads(proof.read_text())}
for item in queries:
    image = root / 'homework/03/screenshots' / (item['id'] + '.png')
    if not image.is_file() or image.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('Missing actual vmui screenshot: ' + str(image))
    entry = evidence.get(item['id'], {})
    if entry.get('query') != item['query'] or entry.get('status') != 200 or not entry.get('rows'):
        raise SystemExit('Missing successful vmui execution proof: ' + item['id'])
files = {}
excluded = {'node_modules', 'dist', '.venv', '__pycache__', '.git'}
for folder in ['services/taskboard', 'deploy', 'homework/03']:
    for path in sorted((root / folder).rglob('*')):
        if path.is_file() and not set(path.parts) & excluded and path.name != '.env':
            files[str(path.relative_to(root))] = path
for path in sorted((root / 'scripts').glob('*')):
    if path.is_file():
        files['scripts/' + path.name] = path
files['Makefile'] = root / 'Makefile'
files['README.md'] = root / 'homework/03/README.md'
files['Отчёт.md'] = root / 'homework/03/Отчёт.md'
files['homework/02/.env.example'] = root / 'homework/02/.env.example'
for item in queries:
    files['screenshots/' + item['id'] + '.png'] = root / 'homework/03/screenshots' / (item['id'] + '.png')
files['deploy/logging/rendered.yaml'] = rendered
files['vmui-queries.json'] = proof
verification = root / 'artifacts/hw03/verification.json'
if verification.is_file():
    files['verification.json'] = verification
output = root / 'artifacts/homework-03.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name, path in sorted(files.items()):
        archive.write(path, name)
print(str(output) + ' (4 verified vmui screenshots)')
