"""Gemeinsamer Kontext für Befehle (Einstellungen, Gedächtnis, Programme)."""
import threading
import webbrowser


class Ctx:
    def __init__(self, settings, memory, apps):
        self.settings, self.memory, self.apps = settings, memory, apps
        self.on_mood = lambda m: None
        self.on_clipboard = lambda s: None
        self.on_timer_done = lambda label: None
        self._timers = []

    def set_mood(self, mood):
        self.settings.set("mood", mood)
        self.on_mood(mood)

    def clipboard(self, text):
        self.on_clipboard(text)

    def timer(self, seconds, label):
        t = threading.Timer(seconds, lambda: self.on_timer_done(label))
        t.daemon = True
        t.start()
        self._timers.append(t)

    def open_url(self, url):
        webbrowser.open(url)
