"""Sprachausgabe (Windows-Stimmen via pyttsx3) und Spracherkennung (faster-whisper, lokal)."""
import collections
import re
import threading
import time

STYLES = [  # Name, Tempo-Änderung, Lautstärke
    ("Natürlich", 0, 1.0), ("Sanft", -25, 0.8), ("Ruhig", -40, 0.9), ("Energisch", 45, 1.0),
    ("Tief & stark", -15, 1.0), ("Hart", 15, 1.0), ("Flüstern", -35, 0.35), ("Schnell", 80, 1.0),
]
BASE_RATE = 185


def clean(text):
    text = re.sub(r"[*_#`>~]", "", text)
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", "", text).strip()


class Speaker:
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()
        self._profiles = []

    @staticmethod
    def _com():
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

    def load_profiles(self):
        """Muss in einem Hintergrund-Thread laufen. Stimme x Stil = Profile."""
        try:
            self._com()
            import pyttsx3
            eng = pyttsx3.init()
            voices = eng.getProperty("voices")
            eng.stop()
            de = [v for v in voices if re.search(r"german|deutsch|de-de|de_de", (v.name + v.id), re.I)]
            use = de or voices
            self._profiles = [{"name": f"{re.sub(r'Microsoft | Desktop.*', '', v.name)} – {s}", "id": v.id,
                               "rate": BASE_RATE + dr, "vol": vol} for v in use for s, dr, vol in STYLES]
        except Exception:
            self._profiles = []
        return self._profiles

    @property
    def profiles(self):
        return self._profiles

    def speak(self, text, profile_name="", speed=100, volume=100):
        text = clean(text)
        if not text:
            return
        with self.lock:
            try:
                self._com()
                import pyttsx3
                eng = pyttsx3.init()
                self.engine = eng
                prof = next((p for p in self._profiles if p["name"] == profile_name), None) or \
                    (self._profiles[0] if self._profiles else None)
                if prof:
                    eng.setProperty("voice", prof["id"])
                    eng.setProperty("rate", int(prof["rate"] * (speed or 100) / 100))
                    eng.setProperty("volume", min(1.0, prof["vol"] * (volume or 100) / 100))
                eng.say(text)
                eng.runAndWait()
            except Exception:
                pass
            finally:
                self.engine = None

    def stop(self):
        try:
            if self.engine:
                self.engine.stop()
        except Exception:
            pass


class Listener:
    SR = 16000

    def __init__(self, settings):
        self.s = settings
        self.model = None
        self.model_name = None
        self.cancel = False

    def _load(self):
        name = self.s.get("whisper_model")
        if self.model is None or self.model_name != name:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(name, device="cpu", compute_type="int8")
            self.model_name = name
        return self.model

    def record(self, wait=8.0, max_seconds=20.0):
        """Nimmt auf, bis nach der Sprache eine Pause kommt. None = nichts gehört."""
        import numpy as np
        import sounddevice as sd
        block = int(self.SR * 0.05)
        pre = collections.deque(maxlen=12)  # 0,6 s Vorlauf, damit der Satzanfang nicht fehlt
        frames, noise = [], []
        started, silent, thr = False, 0.0, 0.01
        mult, pause = float(self.s.get("sensitivity")), float(self.s.get("pause"))
        t0 = time.time()
        self.cancel = False
        with sd.InputStream(samplerate=self.SR, channels=1, dtype="float32", blocksize=block,
                            device=self.s.get("mic")) as st:
            while not self.cancel:
                data, _ = st.read(block)
                x = data[:, 0].copy()
                rms = float(np.sqrt(np.mean(x * x)))
                if len(noise) < 8:
                    noise.append(rms)
                    thr = max(0.01, float(np.mean(noise)) * mult)
                    pre.append(x)
                    continue
                if not started:
                    pre.append(x)
                    if rms > thr:
                        started = True
                        frames = list(pre)
                    elif time.time() - t0 > wait:
                        return None
                else:
                    frames.append(x)
                    silent = silent + 0.05 if rms < thr else 0.0
                    if silent >= pause or time.time() - t0 > max_seconds:
                        break
        if not started or self.cancel:
            return None
        return np.concatenate(frames)

    def transcribe(self, audio):
        names = ", ".join(self.s.get("wake_words") + list((self.s.get("games") or {}))[:15])
        segs, _ = self._load().transcribe(audio, language="de", vad_filter=True, beam_size=1,
                                          initial_prompt=f"{names}, Master, öffne, youtube")
        return " ".join(s.text.strip() for s in segs).strip()

    def listen(self, wait=8.0):
        audio = self.record(wait=wait)
        return self.transcribe(audio) if audio is not None else ""
