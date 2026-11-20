"""Build the completely static distribution. No network or npm packages needed."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist"
if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(ROOT / "site", OUT, ignore=shutil.ignore_patterns("_qa-*", ".DS_Store"))
print(f"Built {sum(1 for p in OUT.rglob('*') if p.is_file())} static assets in {OUT}")
