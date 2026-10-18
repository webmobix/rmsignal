"""Artifacts are reached only through the artifact store: no module outside the store, the seed command and the run log
reads, writes, lists or deletes files on a report path."""

import re
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "rm_dashboard"
FILE_OPS = re.compile(r"\.(write_text|read_text|write_bytes|read_bytes|iterdir|glob|rglob|unlink|rmtree)\(|shutil\.|\bopen\(")
ALLOWED = {
    "llmlog.py",           # run.log is an operational log, not an artifact
    "data/seed.py",        # reads the dataset files
    "data/datasource.py",  # opens the source database
    "data/dataset.py",     # reads the dataset files
    "store/sqlite.py",     # the local backend
    "store/folder.py",     # reads an older reports/ folder tree for the loader
}


def test_no_file_operations_on_report_paths_outside_the_store():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in ALLOWED or rel.startswith("static/"):
            continue
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            if FILE_OPS.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, "\n".join(offenders)
