"""Restore curated regression fixtures into the legacy ignored data paths."""
from pathlib import Path
import shutil


def pytest_sessionstart(session):
    root=Path(__file__).resolve().parents[1]
    fixture_root=root/'tests/fixtures'
    for category in ('captures','artifacts'):
        folder=fixture_root/category
        if not folder.exists():continue
        for source in folder.rglob('*'):
            if not source.is_file():continue
            destination=root/category/source.relative_to(folder)
            if destination.exists():continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination)
