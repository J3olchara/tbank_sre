"""Create a source-only submission with the report at the archive root."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
output = root / "artifacts" / "homework-01.zip"
output.parent.mkdir(exist_ok=True)
excluded = {"node_modules", "dist", ".venv", "__pycache__", ".git"}
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted((root / "services" / "taskboard").rglob("*")):
        if path.is_file() and not (set(path.parts) & excluded) and path.name not in {".env", "README.md"}:
            archive.write(path, path.relative_to(root / "services" / "taskboard"))
    for name in ["Отчёт.md", "README.md"]:
        archive.write(root / "homework" / "01" / name, name)
print(output)
