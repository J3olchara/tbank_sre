"""Package actual Grafana exports, screenshots and the real screen recording."""
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

root=Path(__file__).resolve().parents[1]
homework=root/'homework/06'
video=root/'artifacts/homework-06-demo.mp4'
render=root/'artifacts/hw06/grafana-rendered.yaml'
configmap=root/'artifacts/hw06/dashboard-configmap.yaml'
proof_file=root/'artifacts/hw06/grafana-recording.json'
check_file=root/'artifacts/hw06/grafana-check.json'
report=homework/'Отчёт.md'
for path in (video,render,configmap,proof_file,check_file,report):
    if not path.is_file():
        raise SystemExit(f'Missing required artifact: {path}')
duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(video)],text=True))
if not 0<duration<=420:
    raise SystemExit(f'Expected a short real screencast, got {duration:.1f}s')
proof=json.loads(proof_file.read_text())
events={item['event'] for item in proof['events']}
required={'app-overview','app-runtime','app-sla','pg-import','pg-overview','pg-database','complete'}
required.update('verified: '+phase for phase in ('healthy','slow','errors','recovery'))
if not required<=events or not proof['responses'] or any(r['status']!=200 for r in proof['responses']):
    raise SystemExit('Missing successful native Grafana demonstration')
checks=json.loads(check_file.read_text())
if not checks['panels'] or any(not p['samples'] and not(p['dashboard']=='taskboard-overview' and p['panel_id']==33) for p in checks['panels']):
    raise SystemExit('Missing real panel samples')
for name,uid in [('taskboard.json','taskboard-overview'),('postgres.json','taskboard-postgres')]:
    path=homework/'dashboards'/name
    if not path.is_file() or json.loads(path.read_text())['uid']!=uid:
        raise SystemExit('Missing real dashboard export: '+name)
for relative in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report.read_text()):
    path=homework/relative
    if not path.is_file() or path.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':
        raise SystemExit('Missing actual Grafana screenshot: '+relative)
files={}
excluded={'node_modules','dist','.venv','__pycache__','.git'}
for folder in ['services/taskboard','deploy','homework/06']:
    for path in sorted((root/folder).rglob('*')):
        if path.is_file() and not set(path.parts)&excluded and path.name!='.env':
            files[str(path.relative_to(root))]=path
for path in sorted((root/'scripts').glob('*')):
    if path.is_file():
        files['scripts/'+path.name]=path
files.update({'Makefile':root/'Makefile','AGENTS.md':root/'AGENTS.md',
              'project-README.md':root/'README.md',
              'README.md':homework/'README.md','Отчёт.md':report,
              'homework/02/.env.example':root/'homework/02/.env.example',
              'screencast.mp4':video,
              'deploy/grafana/grafana-rendered.yaml':render,
              'deploy/grafana/dashboard-configmap.yaml':configmap})
for path in (homework/'screenshots').glob('*.png'):
    files['screenshots/'+path.name]=path
for path in (homework/'dashboards').glob('*.json'):
    files['dashboards/'+path.name]=path
for path in (root/'artifacts/hw06').glob('*.json'):
    files['verification/'+path.name]=path
output=root/'artifacts/homework-06.zip'
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
    for name,path in sorted(files.items()):
        archive.write(path,name)
print(f'{output}: {duration:.1f}s real screencast, exported JSON, screenshots, sources and manifests')
