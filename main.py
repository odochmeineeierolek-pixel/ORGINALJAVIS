"""Hauptfenster von YAVIS (PySide6)."""
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QSlider, QStackedWidget, QTextEdit, QVBoxLayout, QWidget)

from .. import brain as brainmod
from .. import commands
from ..apps import AppManager
from ..config import Settings, data_dir
from ..context import Ctx
from ..extras import E
from ..memory import Memory
from .. import voices as vc
from ..voice import Listener, Speaker
from .orb import Orb

QSS = """
* { font-family: 'Segoe UI'; font-size: 13px; color: #f2f2f2; }
QMainWindow, QWidget#page { background: #0a0a0a; }
QWidget#side { background: #111111; border-right: 1px solid #2a2a2a; }
QPushButton { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 8px 14px; }
QPushButton:hover { border-color: #e11d2e; }
QPushButton:checked { background: #3a0c10; border-color: #ffd400; color: #ffd400; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 11px 16px; font-size: 14px; }
QPushButton#nav:checked { background: #2a2208; color: #ffd400; border: 1px solid #5a4a10; }
QPushButton#go { background: #ffd400; color: #111; font-weight: bold; border: none; }
QPushButton#stop { background: #e11d2e; border: none; font-weight: bold; }
QLineEdit, QTextEdit, QListWidget, QComboBox, QDoubleSpinBox { background: #141414; border: 1px solid #333;
  border-radius: 8px; padding: 6px; selection-background-color: #e11d2e; }
QLineEdit#big { border: 2px solid #e11d2e; padding: 12px; font-size: 15px; }
QListWidget::item { padding: 6px; } QListWidget::item:selected { background: #3a0c10; color: #ffd400; }
QLabel#h1 { font-size: 22px; font-weight: bold; } QLabel#muted { color: #9a9a9a; }
QSlider::groove:horizontal { height: 6px; background: #333; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #ffd400; border-radius: 3px; }
QSlider::handle:horizontal { background: #e11d2e; width: 14px; margin: -5px 0; border-radius: 7px; }
"""
MOOD_NAMES = {"lieb": "Lieb", "neutral": "Neutral", "boese": "Böse", "traurig": "Traurig"}
AUDIO = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".wma")


class Bus(QObject):
    log = Signal(str, str)
    caption = Signal(str)
    speaking = Signal(bool)
    listening = Signal(bool)
    status = Signal(str)
    profiles = Signal(list)
    clip = Signal(str)
    apps = Signal()
    dl = Signal(str, int)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YAVIS")
        self.resize(1180, 760)
        self.s, self.mem = Settings(), Memory()
        self.apps = AppManager(self.s)
        self.ctx = Ctx(self.s, self.mem, self.apps)
        self.brain = brainmod.Brain(self.s, self.mem)
        self.speaker, self.listener = Speaker(), Listener(self.s)
        self.voices = vc.VoiceManager(self.s, self.speaker)
        self.win_profiles = []
        self.bus = Bus()
        self.lock = threading.Lock()
        self.continuous = False
        self.is_speaking = False
        self.last = ("", "")

        self.ctx.on_mood = lambda m: self.bus.status.emit("")
        self.ctx.on_clipboard = lambda t: self.bus.clip.emit(t)
        self.ctx.on_timer_done = lambda lb: self._async(lambda: self._say(f"Der Timer ist abgelaufen, Master. ({lb})"))
        self.bus.log.connect(self._on_log)
        self.bus.caption.connect(self._on_caption)
        self.bus.speaking.connect(self._on_speaking)
        self.bus.listening.connect(lambda v: setattr(self.orb, "listening", v))
        self.bus.status.connect(lambda _: self._refresh_status())
        self.bus.profiles.connect(self._fill_profiles)
        self.bus.dl.connect(self._on_dl)
        self.bus.apps.connect(lambda: self._fill_apps())
        self.bus.clip.connect(lambda t: QGuiApplication.clipboard().setText(t))

        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        logo = QLabel("YAVIS")
        logo.setObjectName("h1")
        logo.setStyleSheet("color:#ffd400; font-size:28px; letter-spacing:6px; padding:18px 16px;")
        sl.addWidget(logo)
        self.stack = QStackedWidget()
        self.navs = []
        for i, name in enumerate(["Home", "Chat", "Programme", "Musik", "Extras", "Stimmen", "Einstellungen"]):
            b = QPushButton(name)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _, i=i: self._nav(i))
            sl.addWidget(b)
            self.navs.append(b)
        sl.addStretch()
        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("muted")
        self.status_lbl.setWordWrap(True)
        sl.addWidget(self.status_lbl)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        for build in (self._home, self._chat, self._programs, self._music, self._extras, self._voices_page, self._settings):
            self.stack.addWidget(build())
        self._nav(0)

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(self.s.get("volume") / 100)

        self._async(self._startup)
        self.poll = QTimer(self)
        self.poll.timeout.connect(lambda: self._async(self._poll_ollama))
        self.poll.start(15000)

    # ---------- Hilfen ----------
    def _async(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _nav(self, i):
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.navs):
            b.setChecked(k == i)

    def _page(self):
        w = QWidget()
        w.setObjectName("page")
        v = QVBoxLayout(w)
        v.setContentsMargins(26, 22, 26, 22)
        return w, v

    def _startup(self):
        brainmod.try_start_ollama()
        try:
            self.apps.scan_games()
            self.bus.apps.emit()
        except Exception:
            logging.exception("Spiele-Scan")
        self.bus.profiles.emit(self.speaker.load_profiles())
        self._poll_ollama()

    def _poll_ollama(self):
        self.ollama_state = brainmod.ollama_status(self.s)
        self.bus.status.emit("")

    def _refresh_status(self):
        up, has = getattr(self, "ollama_state", (False, False))
        ol = "bereit" if up and has else ("Modell fehlt" if up else "nicht gefunden")
        self.status_lbl.setText(f"Ollama: {ol}\nStimmung: {MOOD_NAMES.get(self.s.get('mood'), '?')}\n"
                                f"Hört auf: {', '.join(self.s.get('wake_words'))}")

    # ---------- Home ----------
    def _home(self):
        w, v = self._page()
        self.orb = Orb()
        v.addWidget(self.orb, 1)
        self.reply_lbl = QLabel("Hallo Master. Schreib mir oder drück das Mikrofon.")
        self.reply_lbl.setWordWrap(True)
        self.reply_lbl.setAlignment(Qt.AlignCenter)
        self.reply_lbl.setStyleSheet("font-size:16px;")
        v.addWidget(self.reply_lbl)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setObjectName("big")
        self.input.setPlaceholderText("Frag mich etwas oder gib einen Befehl, z. B. „öffne YouTube“ …")
        self.input.returnPressed.connect(self._send_input)
        mic = QPushButton("🎤")
        mic.clicked.connect(self._push_to_talk)
        go = QPushButton("Senden")
        go.setObjectName("go")
        go.clicked.connect(self._send_input)
        stop = QPushButton("Stopp")
        stop.setObjectName("stop")
        stop.clicked.connect(self._stop)
        row.addWidget(self.input, 1)
        row.addWidget(mic)
        row.addWidget(go)
        row.addWidget(stop)
        v.addLayout(row)
        row2 = QHBoxLayout()
        self.cont_btn = QPushButton("Dauerhaft zuhören")
        self.cont_btn.setCheckable(True)
        self.cont_btn.clicked.connect(self._toggle_continuous)
        row2.addWidget(self.cont_btn)
        for label, cmd in (("YouTube", "youtube"), ("Spotify", "spotify"), ("Uhrzeit", "uhrzeit"), ("Würfeln", "würfel")):
            b = QPushButton(label)
            b.clicked.connect(lambda _, c=cmd: self.run_text(c))
            row2.addWidget(b)
        row2.addStretch()
        v.addLayout(row2)
        return w

    def _send_input(self):
        t = self.input.text().strip()
        if t:
            self.input.clear()
            self.run_text(t)

    # ---------- Chat ----------
    def _chat(self):
        w, v = self._page()
        h = QLabel("Chat")
        h.setObjectName("h1")
        v.addWidget(h)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        v.addWidget(self.log, 1)
        row = QHBoxLayout()
        up, down = QPushButton("👍 Gut"), QPushButton("👎 Schlecht")
        up.clicked.connect(lambda: self._feedback(1))
        down.clicked.connect(lambda: self._feedback(-1))
        row.addWidget(up)
        row.addWidget(down)
        row.addWidget(QLabel("YAVIS lernt aus deiner Bewertung der letzten Antwort."))
        row.addStretch()
        v.addLayout(row)
        return w

    def _feedback(self, score):
        if self.last[1]:
            self.mem.add_feedback(self.last[0], self.last[1], score)
            self.bus.caption.emit("Danke fürs Feedback, Master" if score > 0 else "Verstanden, ich werde es besser machen")

    def _on_log(self, who, text):
        color = "#ffd400" if who == "YAVIS" else "#e11d2e" if who == "Du" else "#9a9a9a"
        safe = text.replace("<", "&lt;").replace("\n", "<br>")
        self.log.append(f'<p><b style="color:{color}">{who}:</b> {safe}</p>')
        if who == "YAVIS":
            self.reply_lbl.setText(text[:400])

    def _on_caption(self, t):
        self.orb.caption = t

    def _on_speaking(self, v):
        self.orb.speaking = v
        self.is_speaking = v
        self.orb.caption = "Spreche …" if v else "Bereit"

    # ---------- Verarbeitung ----------
    def run_text(self, text, prompt=None, long=False):
        self._async(lambda: self._work(text, prompt, long))

    def _work(self, text, prompt=None, long=False):
        if not self.lock.acquire(blocking=False):
            self.bus.log.emit("System", "Einen Moment, ich bin noch beschäftigt.")
            return
        try:
            self.bus.log.emit("Du", text)
            self.bus.caption.emit("Denke nach …")
            ans = None if prompt else commands.handle(text, self.ctx)
            if ans is None:
                ans = self.brain.reply(prompt or text, long=long)
            self.last = (text, ans)
            self.bus.log.emit("YAVIS", ans)
            self._speak(ans)
        except Exception as e:
            logging.exception("Fehler")
            self.bus.log.emit("System", f"Fehler: {e}")
        finally:
            self.bus.caption.emit("Bereit")
            self.lock.release()

    def _say(self, text):
        self.bus.log.emit("YAVIS", text)
        self._speak(text)

    def _speak(self, text):
        if not self.s.get("speak_replies"):
            return
        self.bus.speaking.emit(True)
        try:
            self.voices.speak(text, notice=lambda m: self.bus.log.emit("System", m))
        finally:
            self.bus.speaking.emit(False)

    def _stop(self):
        self.voices.stop()
        self.listener.cancel = True
        self.continuous = False
        self.cont_btn.setChecked(False)
        self.bus.listening.emit(False)
        self.bus.caption.emit("Gestoppt")

    # ---------- Zuhören ----------
    def _push_to_talk(self):
        def job():
            self.bus.listening.emit(True)
            self.bus.caption.emit("Ich höre zu …")
            try:
                text = self.listener.listen(wait=8)
            except Exception as e:
                self.bus.log.emit("System", f"Mikrofon/Spracherkennung nicht verfügbar: {e}")
                text = ""
            finally:
                self.bus.listening.emit(False)
            if text:
                _, rest = commands.strip_wake(text, self.s.get("wake_words"))
                self.run_text(rest or text)
            else:
                self.bus.caption.emit("Nichts verstanden")
        self._async(job)

    def _toggle_continuous(self, on):
        self.continuous = on
        if on:
            self._async(self._continuous_loop)
        else:
            self.listener.cancel = True

    def _continuous_loop(self):
        self.bus.caption.emit("Warte auf „" + self.s.get("wake_words")[0] + "“ …")
        while self.continuous:
            if self.is_speaking or self.lock.locked():
                threading.Event().wait(0.3)
                continue
            try:
                text = self.listener.listen(wait=4)
            except Exception as e:
                self.bus.log.emit("System", f"Zuhören nicht möglich: {e}")
                break
            if not text or not self.continuous:
                continue
            woke, rest = commands.strip_wake(text, self.s.get("wake_words"))
            if not woke:
                continue
            if rest:
                self.run_text(rest)
            else:
                self.run_text("hallo")

    # ---------- Programme ----------
    def _programs(self):
        w, v = self._page()
        h = QLabel("Programme, die YAVIS starten darf")
        h.setObjectName("h1")
        v.addWidget(h)
        v.addWidget(QLabel("Nur Programme mit Haken werden gestartet. Alles andere lehnt YAVIS ab."))
        self.app_list = QListWidget()
        v.addWidget(self.app_list, 1)
        row = QHBoxLayout()
        for label, fn in (("Spiele scannen", self._scan_games), ("Startmenü scannen", self._scan), ("Alle auswählen", lambda: self._check_all(True)),
                          ("Keine auswählen", lambda: self._check_all(False))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        v.addLayout(row)
        self._fill_apps()
        self.app_list.itemChanged.connect(self._save_apps)
        return w

    def _fill_apps(self):
        self.app_list.blockSignals(True)
        self.app_list.clear()
        allowed = self.apps.allowed()
        for name in sorted(self.apps.all_apps()):
            it = QListWidgetItem(("🎮 " if name in self.apps.games() else "") + name.title())
            it.setData(Qt.UserRole, name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if name in allowed else Qt.Unchecked)
            self.app_list.addItem(it)
        self.app_list.blockSignals(False)

    def _save_apps(self, *_):
        names = [self.app_list.item(i).data(Qt.UserRole) for i in range(self.app_list.count())
                 if self.app_list.item(i).checkState() == Qt.Checked]
        self.apps.set_allowed(names)

    def _check_all(self, on):
        self.app_list.blockSignals(True)
        for i in range(self.app_list.count()):
            self.app_list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.app_list.blockSignals(False)
        self._save_apps()

    def _scan_games(self):
        n = self.apps.scan_games()
        self._fill_apps()
        QMessageBox.information(self, "Spiele-Scan", f"{n} Spiele gefunden (Steam, Epic, GOG) und freigegeben. "
                                "Sag z. B. „Yavis, starte Minecraft“. Haken kannst du hier entfernen." if n else
                                "Keine Spiele von Steam, Epic oder GOG gefunden. Andere Spiele findet der Startmenü-Scan.")

    def _scan(self):
        old = self.apps.allowed()
        n = self.apps.scan()
        self.apps.set_allowed(old)
        self._fill_apps()
        QMessageBox.information(self, "Scan fertig", f"{n} Programme im Startmenü gefunden. Setze die Haken, die YAVIS starten darf.")

    # ---------- Musik ----------
    def _music(self):
        w, v = self._page()
        h = QLabel("Musik")
        h.setObjectName("h1")
        v.addWidget(h)
        top = QHBoxLayout()
        self.music_lbl = QLabel(self.s.get("music_dir") or "Kein Ordner gewählt")
        pick = QPushButton("Musikordner wählen")
        pick.clicked.connect(self._pick_music)
        top.addWidget(self.music_lbl, 1)
        top.addWidget(pick)
        v.addLayout(top)
        self.songs = QListWidget()
        self.songs.itemDoubleClicked.connect(lambda it: self._play(it.data(Qt.UserRole)))
        v.addWidget(self.songs, 1)
        row = QHBoxLayout()
        for label, fn in (("▶ Abspielen", self._play_sel), ("⏸ Pause", lambda: self.player.pause()),
                          ("⏹ Stopp", lambda: self.player.stop()), ("⏭ Weiter", self._next)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        vol = QSlider(Qt.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(self.s.get("volume"))
        vol.valueChanged.connect(self._vol)
        row.addWidget(QLabel("Lautstärke"))
        row.addWidget(vol)
        v.addLayout(row)
        self._scan_music()
        return w

    def _pick_music(self):
        d = QFileDialog.getExistingDirectory(self, "Musikordner wählen", self.s.get("music_dir") or str(Path.home() / "Music"))
        if d:
            self.s.set("music_dir", d)
            self.music_lbl.setText(d)
            self._scan_music()

    def _scan_music(self):
        self.songs.clear()
        d = self.s.get("music_dir")
        if d and Path(d).exists():
            for f in sorted(Path(d).rglob("*")):
                if f.suffix.lower() in AUDIO:
                    it = QListWidgetItem(f.stem)
                    it.setData(Qt.UserRole, str(f))
                    self.songs.addItem(it)

    def _play(self, path):
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _play_sel(self):
        it = self.songs.currentItem() or (self.songs.item(0) if self.songs.count() else None)
        if it:
            self._play(it.data(Qt.UserRole))

    def _next(self):
        r = self.songs.currentRow() + 1
        if r < self.songs.count():
            self.songs.setCurrentRow(r)
            self._play_sel()

    def _vol(self, v):
        self.audio.setVolume(v / 100)
        self.s.set("volume", v)

    # ---------- Extras ----------
    def _extras(self):
        w, v = self._page()
        h = QLabel(f"{len(E)} Extras")
        h.setObjectName("h1")
        v.addWidget(h)
        v.addWidget(QLabel("Doppelklick startet ein Extra. „KI“ braucht Ollama, alles andere läuft sofort."))
        lst = QListWidget()
        for i, e in enumerate(E):
            it = QListWidgetItem(f"{e['cat']}  ·  {e['name']}" + ("   [KI]" if e["kind"] == "ai" else ""))
            it.setData(Qt.UserRole, i)
            lst.addItem(it)
        lst.itemDoubleClicked.connect(lambda it: self._run_extra(E[it.data(Qt.UserRole)]))
        v.addWidget(lst, 1)
        return w

    def _run_extra(self, e):
        inp = ""
        if e["ask"]:
            inp, ok = QInputDialog.getText(self, e["name"], e["ask"])
            if not ok or not inp.strip():
                return
        text = e["text"].replace("{input}", inp).strip()
        self._nav(0)
        if e["kind"] == "cmd":
            self.run_text(text)
        else:
            self.run_text(e["name"] + (": " + inp if inp else ""), prompt=text, long=True)

    # ---------- Stimmen ----------
    def _voices_page(self):
        w, v = self._page()
        h = QLabel(f"Stimmen ({len(vc.PROFILES)} Profile)")
        h.setObjectName("h1")
        v.addWidget(h)
        info = QLabel("Piper läuft offline und kostenlos. Jede Stimme wird beim ersten Mal einmalig geladen "
                      "(20–110 MB).  ✓ = bereit, ⬇ = noch nicht geladen, ★ = aktiv.")
        info.setWordWrap(True)
        v.addWidget(info)
        top = QHBoxLayout()
        self.v_filter = QComboBox()
        self.v_filter.addItems(["Alle", "Weiblich", "Männlich", "Gefühle", "Windows"])
        self.v_filter.currentIndexChanged.connect(self._fill_voice_list)
        top.addWidget(QLabel("Filter"))
        top.addWidget(self.v_filter)
        top.addStretch()
        v.addLayout(top)
        self.v_list = QListWidget()
        self.v_list.itemDoubleClicked.connect(lambda _: self._voice_preview())
        v.addWidget(self.v_list, 1)

        def slider(label, key, lo, hi, unit):
            r = QHBoxLayout()
            lb = QLabel()
            lb.setFixedWidth(220)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(int(self.s.get(key)))
            lb.setText(f"{label}: {sl.value()}{unit}")
            sl.valueChanged.connect(lambda val: (self.s.set(key, val), lb.setText(f"{label}: {val}{unit}")))
            r.addWidget(lb)
            r.addWidget(sl, 1)
            v.addLayout(r)
            return sl

        self.sl_speed = slider("Sprechtempo", "voice_speed", 50, 160, " %")
        self.sl_pitch = slider("Tonhöhe (Halbtöne)", "voice_pitch", -6, 6, "")
        self.sl_vol = slider("Lautstärke", "voice_volume", 30, 150, " %")
        note = QLabel("Tonhöhe wirkt nur bei Piper-Stimmen. Windows-Stimmen unterstützen nur Tempo und Lautstärke.")
        note.setObjectName("muted")
        v.addWidget(note)
        row = QHBoxLayout()
        for label, fn in (("▶ Vorschau", self._voice_preview), ("✔ Auswählen", self._voice_choose),
                          ("⬇ Diese Stimme laden", self._voice_download),
                          ("⬇ Alle laden (ca. 0,5 GB)", self._voice_download_all),
                          ("Regler zurücksetzen", self._voice_reset)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.dl_lbl = QLabel("")
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100)
        self.dl_bar.setTextVisible(False)
        self.dl_bar.setFixedHeight(8)
        v.addWidget(self.dl_lbl)
        v.addWidget(self.dl_bar)
        self._fill_voice_list()
        return w

    def _fill_voice_list(self, *_):
        if not hasattr(self, "v_list"):
            return
        flt = self.v_filter.currentText()
        cur = self.s.get("voice_profile") or vc.DEFAULT_PROFILE
        keep = self._voice_sel()
        self.v_list.clear()
        names = [p["name"] for p in vc.PROFILES if flt in ("Alle", p["group"])]
        if flt in ("Alle", "Windows"):
            names += self.win_profiles
        for n in names:
            prof = vc.profile_by_name(n)
            ok = self.voices.piper.ready(prof) if prof else True
            it = QListWidgetItem(("★ " if n == cur else "") + ("✓ " if ok else "⬇ ") + n)
            it.setData(Qt.UserRole, n)
            self.v_list.addItem(it)
            if n == keep:
                self.v_list.setCurrentItem(it)

    def _voice_sel(self):
        it = self.v_list.currentItem() if hasattr(self, "v_list") else None
        return it.data(Qt.UserRole) if it else None

    def _voice_choose(self):
        n = self._voice_sel()
        if n:
            self.s.set("voice_profile", n)
            self._fill_voice_list()
            self.dl_lbl.setText(f"Aktive Stimme: {n}")

    def _voice_reset(self):
        self.sl_speed.setValue(100)
        self.sl_pitch.setValue(0)
        self.sl_vol.setValue(100)

    def _on_dl(self, text, pct):
        self.dl_lbl.setText(text)
        self.dl_bar.setValue(pct)
        if pct >= 100 or text.startswith("Fehler"):
            self._fill_voice_list()

    def _dl_job(self, profiles, then=None):
        def job():
            pip = self.voices.piper
            try:
                steps = (["engine"] if not pip.has_engine() else []) + \
                    sorted({p["base"] for p in profiles if not pip.has_model(p["base"])})
                for i, st in enumerate(steps):
                    label = "Sprach-Engine" if st == "engine" else f"Stimme {vc.model_id(st)}"
                    msg = f"Lade {label} ({i + 1}/{len(steps)}) …"
                    self.bus.dl.emit(msg, 0)

                    def cb(f, msg=msg):
                        self.bus.dl.emit(msg, int(f * 99))
                    pip.ensure_engine(cb) if st == "engine" else pip.ensure_model(st, cb)
                self.bus.dl.emit("Fertig geladen.", 100)
                if then:
                    then()
            except Exception as e:
                self.bus.dl.emit(f"Fehler beim Laden: {e}. Prüfe die Internetverbindung.", 0)
        self._async(job)

    def _voice_download(self):
        prof = vc.profile_by_name(self._voice_sel() or "")
        if prof:
            self._dl_job([prof])

    def _voice_download_all(self):
        if QMessageBox.question(self, "Alle Stimmen laden",
                                "Das sind ungefähr 0,5 Gigabyte. Fortfahren?") == QMessageBox.Yes:
            self._dl_job(vc.PROFILES)

    def _voice_preview(self):
        name = self._voice_sel()
        if not name:
            return
        prof = vc.profile_by_name(name)

        def speak():
            self.bus.speaking.emit(True)
            try:
                if prof is None:
                    self.speaker.speak(vc.SAMPLE, name.replace("Windows · ", ""),
                                       speed=self.s.get("voice_speed"), volume=self.s.get("voice_volume"))
                else:
                    with self.voices.piper.lock:
                        path, dur = self.voices.piper.synth(prof, vc.SAMPLE, self.s.get("voice_speed"),
                                                            self.s.get("voice_pitch"), self.s.get("voice_volume"))
                        self.voices.piper.play(path, dur)
            except Exception as e:
                self.bus.dl.emit(f"Fehler bei der Vorschau: {e}", 0)
            finally:
                self.bus.speaking.emit(False)
        if prof is not None and not self.voices.piper.ready(prof):
            self._dl_job([prof], then=speak)
        else:
            self._async(speak)

    # ---------- Einstellungen ----------
    def _settings(self):
        w, v = self._page()
        h = QLabel("Einstellungen")
        h.setObjectName("h1")
        v.addWidget(h)

        def row(label, widget):
            r = QHBoxLayout()
            lb = QLabel(label)
            lb.setFixedWidth(210)
            r.addWidget(lb)
            r.addWidget(widget, 1)
            v.addLayout(r)

        self.f_wake = QLineEdit(", ".join(self.s.get("wake_words")))
        row("Aktivierungsnamen (Komma)", self.f_wake)
        self.f_mood = QComboBox()
        for k, n in MOOD_NAMES.items():
            self.f_mood.addItem(n, k)
        self.f_mood.setCurrentIndex(max(0, self.f_mood.findData(self.s.get("mood"))))
        row("Stimmung", self.f_mood)
        v.addWidget(QLabel("Stimme, Tempo, Tonhöhe und Lautstärke stellst du unter „Stimmen“ ein."))
        self.f_speak = QCheckBox("Antworten vorlesen")
        self.f_speak.setChecked(bool(self.s.get("speak_replies")))
        v.addWidget(self.f_speak)
        self.f_model = QLineEdit(self.s.get("model"))
        row("Ollama-Modell", self.f_model)
        self.f_whisper = QComboBox()
        self.f_whisper.addItems(["tiny", "base", "small"])
        self.f_whisper.setCurrentText(self.s.get("whisper_model"))
        row("Erkennungsmodell", self.f_whisper)
        self.f_sens = QDoubleSpinBox()
        self.f_sens.setRange(1.2, 8.0)
        self.f_sens.setSingleStep(0.2)
        self.f_sens.setValue(float(self.s.get("sensitivity")))
        row("Mikro-Schwelle (niedrig = empfindlicher)", self.f_sens)
        self.f_pause = QDoubleSpinBox()
        self.f_pause.setRange(0.4, 3.0)
        self.f_pause.setSingleStep(0.1)
        self.f_pause.setValue(float(self.s.get("pause")))
        row("Pause am Satzende (Sek.)", self.f_pause)
        btns = QHBoxLayout()
        for label, fn in (("Speichern", self._save_settings), ("Mikrofon testen", self._test_mic),
                          ("Gedächtnis ansehen / löschen", self._memory_dialog)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            btns.addWidget(b)
        v.addLayout(btns)
        v.addStretch()
        return w

    def _fill_profiles(self, profiles):
        self.win_profiles = ["Windows · " + p["name"] for p in profiles]
        self._fill_voice_list()

    def _save_settings(self):
        words = [x.strip().lower() for x in self.f_wake.text().split(",") if x.strip()]
        self.s.set("wake_words", words or ["yavis"])
        self.s.set("mood", self.f_mood.currentData())
        self.s.set("speak_replies", self.f_speak.isChecked())
        self.s.set("model", self.f_model.text().strip() or "llama3.2:3b")
        self.s.set("whisper_model", self.f_whisper.currentText())
        self.s.set("sensitivity", self.f_sens.value())
        self.s.set("pause", self.f_pause.value())
        self._refresh_status()
        QMessageBox.information(self, "Gespeichert", "Einstellungen gespeichert.")

    def _test_mic(self):
        self.s.set("sensitivity", self.f_sens.value())
        self.s.set("pause", self.f_pause.value())
        self.s.set("whisper_model", self.f_whisper.currentText())

        def job():
            self.bus.log.emit("System", "Mikrofontest: Sag in den nächsten Sekunden einen Satz …")
            self.bus.caption.emit("Sprich jetzt …")
            try:
                t = self.listener.listen(wait=6)
                self.bus.log.emit("System", f"Verstanden: „{t}“" if t else "Nichts gehört. Senke die Schwelle oder wähle ein anderes Mikrofon in Windows.")
            except Exception as e:
                self.bus.log.emit("System", f"Mikrofontest fehlgeschlagen: {e}")
            self.bus.caption.emit("Bereit")
        self._nav(1)
        self._async(job)

    def _memory_dialog(self):
        rows = self.mem.list()
        items = [f"{r[0]} · {r[1]} · {r[2]}" for r in rows] or ["(leer)"]
        text, ok = QInputDialog.getItem(self, "Gedächtnis", "Eintrag wählen, um ihn zu löschen:", items, 0, False)
        if ok and rows:
            self.mem.delete(int(text.split(" · ")[0]))
        if QMessageBox.question(self, "Alles löschen?", "Soll das komplette Gedächtnis (inkl. Feedback) gelöscht werden?") == QMessageBox.Yes:
            self.mem.clear_all()

    def closeEvent(self, e):
        self.continuous = False
        self.listener.cancel = True
        self.voices.stop()
        e.accept()


def run():
    logging.basicConfig(filename=str(data_dir() / "yavis.log"), level=logging.INFO)
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
