"""Package the metrics implementation, all manifests, report and real screencast."""
import argparse
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

parser = argparse.ArgumentParser()
parser.add_argument('--video', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
video = args.video or root / 'artifacts/homework-04-demo.mp4'
rendered = root / 'artifacts/hw04/victoriametrics-rendered.yaml'
if not video.is_file() or not rendered.is_file():
    raise SystemExit('Run make monitoring-render and record artifacts/homework-04-demo.mp4 first')
seconds = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video)], text=True))
if not 0 < seconds <= 420:
    raise SystemExit(f'Screencast exceeds 7 minutes: {seconds:.1f}s')
output = root / 'artifacts/homework-04.zip'
excluded = {'node_modules', 'dist', '.venv', '__pycache__', '.git'}
files = {}
for folder in ['services/taskboard', 'deploy', 'homework/04']:
    for path in sorted((root / folder).rglob('*')):
        if path.is_file() and not (set(path.parts) & excluded) and path.name != '.env':
            files[str(path.relative_to(root))] = path
for path in sorted((root / 'scripts').glob('*')):
    if path.is_file():
        files['scripts/' + path.name] = path
files['Makefile'] = root / 'Makefile'
files['homework/02/.env.example'] = root / 'homework/02/.env.example'
files['README.md'] = root / 'homework/04/README.md'
files['Отчёт.md'] = root / 'homework/04/Отчёт.md'
files['screencast.mp4'] = video
files['deploy/monitoring/rendered.yaml'] = rendered
verification = root / 'artifacts/hw04/verification.json'
if verification.is_file():
    files['verification.json'] = verification
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name, path in sorted(files.items()):
        archive.write(path, name)
print(f'{output} ({seconds:.1f}s screencast)')
