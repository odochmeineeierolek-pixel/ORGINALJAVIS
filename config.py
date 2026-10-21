"""Einstellungen (lokale JSON-Datei in %APPDATA%\\YAVIS)."""
import json
import os
from pathlib import Path


def data_dir() -> Path:
    custom = os.environ.get("YAVIS_HOME")
    if custom:
        base = Path(custom)
    else:
        base = Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "YAVIS"
    base.mkdir(parents=True, exist_ok=True)
    return base


DEFAULTS = {
    "wake_words": ["yavis", "jarvis"],
    "mood": "lieb",
    "voice_profile": "",
    "speak_replies": True,
    "model": "llama3.2:3b",
    "ollama_host": "http://127.0.0.1:11434",
    "whisper_model": "base",
    "sensitivity": 3.0,
    "pause": 0.9,
    "mic": None,
    "music_dir": "",
    "allowed_apps": None,   # None = alle Standard-Programme erlaubt
    "scanned_apps": {},
    "volume": 70,
    "voice_speed": 100,
    "voice_pitch": 0,
    "voice_volume": 100,
}


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        try:
            if self.path.exists():
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
