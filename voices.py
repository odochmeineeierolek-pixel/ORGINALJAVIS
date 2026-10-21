"""Piper-Stimmen: Katalog, Download-Verwaltung, Sprachausgabe mit Tempo/Tonhöhe/Lautstärke."""
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
import wave
import zipfile
from pathlib import Path

from .config import data_dir

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/"
PIPER_ZIP = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
# Basisstimme -> (Sprecher-Ordner, Qualität, ungefähre Größe in MB)
BASES = {
    "eva": ("eva_k", "x_low", 20), "kerstin": ("kerstin", "low", 60), "ramona": ("ramona", "low", 60),
    "karlsson": ("karlsson", "low", 60), "pavoque": ("pavoque", "low", 60),
    "thorsten": ("thorsten", "medium", 63), "thorsten_hoch": ("thorsten", "high", 110),
    "emo": ("thorsten_emotional", "medium", 77),
}
SAMPLE = "Hallo Master, so klinge ich. Wie gefällt dir meine Stimme?"

PROFILES = []


def _p(group, label, base, pitch=0.0, length=1.0, vol=1.0, speaker=None):
    PROFILES.append({"name": f"{group} · {label}", "group": group, "base": base, "pitch": pitch,
                     "length": length, "vol": vol, "speaker": speaker})


for lb, pi, ln, vo in (("freundlich", 0, 1.0, 1), ("fröhlich", 1.5, 0.9, 1), ("jung & frisch", 3, 0.92, 1),
                       ("leise & sanft", 0, 1.15, 0.6), ("energisch", 1, 0.8, 1)):
    _p("Weiblich", "Eva – " + lb, "eva", pi, ln, vo)
for lb, pi, ln, vo in (("warm", 0, 1.05, 1), ("mütterlich", -1, 1.15, 1), ("liebevoll", -0.5, 1.22, 0.9),
                       ("ruhig", 0, 1.3, 1), ("professionell", 0.5, 0.95, 1), ("freundlich", 1, 1.0, 1)):
    _p("Weiblich", "Kerstin – " + lb, "kerstin", pi, ln, vo)
for lb, pi, ln, vo in (("selbstbewusst", 0, 0.95, 1), ("tief", -2, 1.05, 1), ("sinnlich", -2, 1.28, 0.85),
                       ("reif & mütterlich", -1.5, 1.12, 1), ("geheimnisvoll", -2.5, 1.3, 0.7),
                       ("energisch", 1, 0.85, 1)):
    _p("Weiblich", "Ramona – " + lb, "ramona", pi, ln, vo)
for lb, b, pi, ln, vo in (("neutral", "thorsten", 0, 1.0, 1), ("professionell", "thorsten_hoch", 0, 0.95, 1),
                          ("warm", "thorsten_hoch", -0.5, 1.05, 1), ("freundlich", "thorsten", 0.5, 1.0, 1),
                          ("dynamisch", "thorsten_hoch", 0.5, 0.85, 1), ("souverän", "thorsten_hoch", -1, 1.05, 1),
                          ("ruhig", "thorsten", 0, 1.25, 1)):
    _p("Männlich", "Thorsten – " + lb, b, pi, ln, vo)
for lb, pi, ln, vo in (("tief", -2, 1.0, 1), ("kräftig", -1.5, 0.95, 1), ("warm", -0.5, 1.08, 1),
                       ("dominant", -3, 1.05, 1), ("ruhig & tief", -2, 1.25, 1)):
    _p("Männlich", "Karlsson – " + lb, "karlsson", pi, ln, vo)
for lb, pi, ln, vo in (("kräftig", 0, 0.95, 1), ("sehr tief", -3.5, 1.08, 1), ("hart", -2, 0.9, 1.15),
                       ("freundlich", 0.5, 1.0, 1), ("dynamisch", 1, 0.85, 1)):
    _p("Männlich", "Pavoque – " + lb, "pavoque", pi, ln, vo)
for lb, sp, pi, ln, vo in (("neutral", "neutral", 0, 1.0, 1), ("fröhlich", "amused", 0, 0.95, 1),
                           ("wütend", "angry", -0.5, 0.9, 1.1), ("müde", "sleepy", 0, 1.1, 0.9),
                           ("flüsternd", "whisper", 0, 1.05, 1), ("überrascht", "surprised", 0.5, 0.95, 1),
                           ("angewidert", "disgusted", 0, 1.0, 1), ("betrunken (Spaß)", "drunk", 0, 1.05, 1),
                           ("traurig", "sleepy", -1.5, 1.22, 0.9), ("ernst", "neutral", -1, 1.1, 1),
                           ("geheimnisvoll", "whisper", -1, 1.12, 1)):
    _p("Gefühle", "Thorsten – " + lb, "emo", pi, ln, vo, sp)

DEFAULT_PROFILE = "Weiblich · Kerstin – warm"


def profile_by_name(name):
    return next((p for p in PROFILES if p["name"] == name), None)


def model_id(base):
    v, q, _ = BASES[base]
    return f"de_DE-{v}-{q}"


def model_url(base):
    v, q, _ = BASES[base]
    return f"{HF}{v}/{q}/{model_id(base)}.onnx"


def plan(profile, speed=100, pitch=0, volume=100):
    """Rechnet Profil + Regler in (length_scale, Abspielrate-Faktor, Verstärkung) um.
    Tonhöhe wird durch geänderte Abspielrate erzeugt (Tempo ändert sich mit), das gleicht length_scale aus."""
    semis = max(-8.0, min(8.0, profile["pitch"] + pitch))
    f = 2 ** (semis / 12)
    length = profile["length"] * f / max(0.4, speed / 100)
    gain = max(0.0, profile["vol"] * volume / 100)
    return length, f, gain


def process_wav(src, dst, factor, gain):
    """Schreibt die WAV mit Lautstärke und neuer Abspielrate (= Tonhöhe) neu. Gibt die Dauer zurück."""
    import numpy as np
    with wave.open(str(src), "rb") as r:
        ch, sw, sr, n = r.getnchannels(), r.getsampwidth(), r.getframerate(), r.getnframes()
        raw = r.readframes(n)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) * gain
    a = np.clip(a, -32768, 32767).astype(np.int16)
    new_sr = int(sr * factor)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(sw)
        w.setframerate(new_sr)
        w.writeframes(a.tobytes())
    return len(a) / ch / new_sr


class Piper:
    def __init__(self):
        self.root = data_dir()
        self.exe = self.root / "piper" / "piper.exe"
        self.models = self.root / "voices"
        self.models.mkdir(exist_ok=True)
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()

    def has_engine(self):
        return self.exe.exists()

    def has_model(self, base):
        m = self.models / (model_id(base) + ".onnx")
        return m.exists() and Path(str(m) + ".json").exists()

    def ready(self, profile):
        return self.has_engine() and self.has_model(profile["base"])

    @staticmethod
    def _download(url, dest, cb=None):
        dest = Path(dest)
        tmp = dest.with_suffix(dest.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "YAVIS"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if cb and total:
                    cb(done / total)
        os.replace(tmp, dest)

    def ensure_engine(self, cb=None):
        if self.has_engine():
            return
        z = self.root / "piper.zip"
        self._download(PIPER_ZIP, z, cb)
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if os.path.isabs(n) or ".." in Path(n).parts:
                    raise ValueError("Unsicheres ZIP")
            zf.extractall(self.root)
        z.unlink(missing_ok=True)

    def ensure_model(self, base, cb=None):
        if self.has_model(base):
            return
        url = model_url(base)
        dest = self.models / (model_id(base) + ".onnx")
        self._download(url + ".json", str(dest) + ".json")
        self._download(url, dest, cb)

    def _speaker_id(self, base, name):
        if name is None:
            return None
        try:
            cfg = json.loads(Path(str(self.models / (model_id(base) + ".onnx")) + ".json").read_text(encoding="utf-8"))
            m = cfg.get("speaker_id_map") or {}
            for k, v in m.items():
                if name in k.lower():
                    return v
        except Exception:
            pass
        return 0

    def synth(self, profile, text, speed=100, pitch=0, volume=100):
        """Erzeugt eine WAV-Datei und gibt (Pfad, Dauer) zurück."""
        length, factor, gain = plan(profile, speed, pitch, volume)
        out = Path(tempfile.gettempdir()) / f"yavis_{os.getpid()}_{int(time.time() * 1000)}"
        raw, fin = str(out) + "_raw.wav", str(out) + ".wav"
        cmd = [str(self.exe), "--model", str(self.models / (model_id(profile["base"]) + ".onnx")),
               "--output_file", raw, "--length_scale", f"{length:.3f}", "--sentence_silence", "0.2"]
        sid = self._speaker_id(profile["base"], profile["speaker"])
        if sid is not None:
            cmd += ["--speaker", str(sid)]
        flags = 0x08000000 if os.name == "nt" else 0
        p = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, cwd=str(self.exe.parent),
                           creationflags=flags, timeout=120)
        if p.returncode != 0 or not os.path.exists(raw):
            raise RuntimeError("Piper-Fehler: " + p.stderr.decode("utf-8", "ignore")[-200:])
        dur = process_wav(raw, fin, factor, gain)
        os.remove(raw)
        return fin, dur

    def play(self, path, dur):
        import winsound
        self.stop_flag.clear()
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        t0 = time.time()
        while time.time() - t0 < dur + 0.1 and not self.stop_flag.is_set():
            time.sleep(0.05)
        if self.stop_flag.is_set():
            winsound.PlaySound(None, winsound.SND_PURGE)
        try:
            os.remove(path)
        except OSError:
            pass

    def stop(self):
        self.stop_flag.set()


class VoiceManager:
    """Wählt automatisch: Piper-Stimme, sonst Windows-Stimme als Rückfall."""

    def __init__(self, settings, sapi):
        self.s, self.sapi, self.piper = settings, sapi, Piper()
        self.notified = False

    def current(self):
        return profile_by_name(self.s.get("voice_profile") or DEFAULT_PROFILE)

    def speak(self, text, profile_name=None, notice=None):
        from .voice import clean
        text = clean(text)
        if not text:
            return
        prof = profile_by_name(profile_name) if profile_name else self.current()
        sp, pi, vo = self.s.get("voice_speed"), self.s.get("voice_pitch"), self.s.get("voice_volume")
        with self.piper.lock:
            if prof and self.piper.ready(prof):
                try:
                    path, dur = self.piper.synth(prof, text, sp, pi, vo)
                    self.piper.play(path, dur)
                    return
                except Exception:
                    pass
            if notice and not self.notified:
                self.notified = True
                notice("Für die gewählte Stimme fehlt noch der Download. Ich nutze vorerst die Windows-Stimme. "
                       "Unter „Stimmen“ kannst du sie laden.")
        win = self.s.get("voice_profile") if (self.s.get("voice_profile") or "").startswith("Windows") else ""
        self.sapi.speak(text, win.replace("Windows · ", ""), speed=sp, volume=vo)

    def stop(self):
        self.piper.stop()
        self.sapi.stop()
