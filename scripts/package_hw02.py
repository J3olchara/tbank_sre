"""Package all build/deployment sources, report and the real <=7 minute video."""
import argparse
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

parser = argparse.ArgumentParser()
parser.add_argument("--video", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
video = args.video or root / "artifacts" / "homework-02-demo.mp4"
if not video.is_file():
    raise SystemExit("Missing screencast: record artifacts/homework-02-demo.mp4 first")
seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video)], text=True))
if not 0 < seconds <= 420:
    raise SystemExit(f"Screencast must be <=420 seconds, got {seconds:.1f}")
output = root / "artifacts" / "homework-02.zip"
excluded = {"node_modules", "dist", ".venv", "__pycache__", ".git"}
files = {}
for folder in ["services/taskboard", "deploy/k8s", "homework/02"]:
    for path in sorted((root / folder).rglob("*")):
        if path.is_file() and not (set(path.parts) & excluded) and path.name != ".env":
            files[str(path.relative_to(root))] = path
for name in ["install_k8s_tools.sh", "k8s.sh", "package_hw02.py", "record_hw02.py", "demo_terminal.py", "demo_ui.cjs"]:
    files["scripts/" + name] = root / "scripts" / name
files["Makefile"] = root / "Makefile"
files["README.md"] = root / "homework/02/README.md"
files["Отчёт.md"] = root / "homework/02/Отчёт.md"
files["screencast.mp4"] = video
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name, path in sorted(files.items()):
        archive.write(path, name)
print(f"{output} ({seconds:.1f}s screencast)")
