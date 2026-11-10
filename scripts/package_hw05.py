"""Package SLO sources, report, actual charts and a verified real screencast."""
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
video = root / 'artifacts/homework-05-demo.mp4'
rendered = root / 'artifacts/hw05/victoriametrics-rendered.yaml'
recording = root / 'artifacts/hw05/vmui-recording.json'
for path in (video, rendered, recording):
    if not path.is_file():
        raise SystemExit(f'Missing required artifact: {path}; run slo-render and record_hw05.py')
seconds = float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(video)],text=True))
if not 0 < seconds <= 420:
    raise SystemExit(f'Invalid screencast duration: {seconds:.1f}s')
proof = json.loads(recording.read_text())
events = {item['event'] for item in proof['events']}
for phase in ('healthy','slow','errors','recovery'):
    if 'verified: ' + phase not in events:
        raise SystemExit('Missing real phase verification: ' + phase)
    if not (root / f'artifacts/hw05/{phase}.json').is_file():
        raise SystemExit('Missing phase sample: ' + phase)
if not proof['responses'] or any(item['status'] != 200 or not item['result'] for item in proof['responses']):
    raise SystemExit('Missing successful vmui query responses')
report = root / 'homework/05/Отчёт.md'
for relative in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', report.read_text()):
    path = report.parent / relative
    if not path.is_file() or path.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('Missing actual chart screenshot: ' + relative)
files = {}
excluded = {'node_modules','dist','.venv','__pycache__','.git'}
for folder in ['services/taskboard','deploy','homework/05']:
    for path in sorted((root / folder).rglob('*')):
        if path.is_file() and not set(path.parts) & excluded and path.name != '.env':
            files[str(path.relative_to(root))] = path
for path in sorted((root / 'scripts').glob('*')):
    if path.is_file():
        files['scripts/' + path.name] = path
files['Makefile'] = root / 'Makefile'
files['docs/defense.md'] = root / 'docs/defense.md'
files['homework/02/.env.example'] = root / 'homework/02/.env.example'
files['README.md'] = root / 'homework/05/README.md'
files['Отчёт.md'] = report
files['screencast.mp4'] = video
files['deploy/slo/victoriametrics-rendered.yaml'] = rendered
for path in (root / 'homework/05/screenshots').glob('*.png'):
    files['screenshots/' + path.name] = path
for path in (root / 'artifacts/hw05').glob('*.json'):
    files['verification/' + path.name] = path
output = root / 'artifacts/homework-05.zip'
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
    for name,path in sorted(files.items()):
        archive.write(path,name)
print(f'{output} ({seconds:.1f}s real screencast, 4 verified phases)')
