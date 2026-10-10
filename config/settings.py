import json
import os
import sys
from pathlib import Path

def resource_root():
    return Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parents[1]))

def settings_path():
    if getattr(sys,"frozen",False):
        folder=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"ShopeePuzzleSolver"
        folder.mkdir(parents=True,exist_ok=True)
        return folder/"settings.json"
    return resource_root()/"config"/"settings.json"

def load_settings():
    path=settings_path()
    template=resource_root()/"config"/"settings.json"
    if not template.exists():template=resource_root()/"config"/"settings.example.json"
    defaults=json.loads(template.read_text(encoding="utf-8-sig"))
    if path.exists(): defaults.update(json.loads(path.read_text(encoding="utf-8-sig")))
    if not 2<=defaults["size"]<=16: raise ValueError("Board size must be 2..16")
    return defaults

def save_settings(settings):
    settings_path().write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf8")
