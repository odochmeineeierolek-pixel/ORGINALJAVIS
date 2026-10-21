"""Programmfreigabe: YAVIS startet nur, was in der Liste freigegeben ist."""
import difflib
import os
import re
import subprocess
import webbrowser
from pathlib import Path

DEFAULT_APPS = {
    "rechner": "calc.exe", "editor": "notepad.exe", "explorer": "explorer.exe",
    "task-manager": "taskmgr.exe", "einstellungen": "ms-settings:", "snipping-tool": "ms-screenclip:",
    "paint": "mspaint.exe", "systemsteuerung": "control.exe", "wlan": "ms-settings:network-wifi",
    "bluetooth": "ms-settings:bluetooth", "sound": "ms-settings:sound", "bildschirm": "ms-settings:display",
    "apps und features": "ms-settings:appsfeatures", "windows update": "ms-settings:windowsupdate",
    "geräte-manager": "devmgmt.msc", "datenträgerverwaltung": "diskmgmt.msc",
    "ressourcenmonitor": "resmon.exe", "zeichentabelle": "charmap.exe", "bildschirmtastatur": "osk.exe",
    "lupe": "magnify.exe", "windows-sicherheit": "windowsdefender:", "e-mail": "mailto:",
    "chrome": "chrome", "firefox": "firefox", "edge": "msedge", "discord": "discord:",
    "steam": "steam:", "xbox": "xbox:", "epic games": "com.epicgames.launcher:",
    "microsoft store": "ms-windows-store:", "fotos": "ms-photos:", "kamera": "microsoft.windows.camera:",
    "uhr": "ms-clock:", "karten": "bingmaps:",
}

WEB = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "spotify": "https://open.spotify.com", "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv", "github": "https://github.com",
    "gmail": "https://mail.google.com", "wikipedia": "https://de.wikipedia.org",
    "maps": "https://www.google.com/maps",
}
SEARCH = {
    "youtube": "https://www.youtube.com/results?search_query=",
    "google": "https://www.google.com/search?q=",
    "spotify": "https://open.spotify.com/search/",
    "wikipedia": "https://de.wikipedia.org/w/index.php?search=",
}

_FILLER = re.compile(r"\b(den|die|das|dem|mein|meinen|meine|bitte|mal|app|programm|spiel)\b")
_SKIP = re.compile(r"uninstall|deinstall|readme|hilfe|help|website|webseite|license|lizenz", re.I)


class AppManager:
    def __init__(self, settings):
        self.settings = settings

    def all_apps(self):
        d = dict(DEFAULT_APPS)
        d.update(self.settings.get("scanned_apps") or {})
        d.update(self.settings.get("games") or {})
        return d

    def games(self):
        return self.settings.get("games") or {}

    def scan_games(self):
        """Findet Steam-, Epic- und GOG-Spiele. Neu gefundene Spiele werden automatisch freigegeben."""
        from .games import scan_all
        found = scan_all()
        old = set(self.games())
        allowed = self.allowed()
        self.settings.set("games", found)
        self.set_allowed(allowed | (set(found) - old))
        return len(found)

    def allowed(self):
        a = self.settings.get("allowed_apps")
        return set(DEFAULT_APPS) if a is None else set(a)

    def set_allowed(self, names):
        self.settings.set("allowed_apps", sorted(set(names)))

    def find(self, query):
        q = _FILLER.sub(" ", query.lower())
        q = re.sub(r"\s+", " ", q).strip(" .,!?")
        if not q:
            return None
        apps = self.all_apps()
        if q in apps:
            return q
        if q in ("taschenrechner", "calculator"):
            return "rechner"
        for n in apps:
            if n.startswith(q):
                return n
        for n in apps:
            if q in n:
                return n
        m = difflib.get_close_matches(q, list(apps), n=1, cutoff=0.75)
        return m[0] if m else None

    def launch(self, query):
        name = self.find(query)
        if name is None:
            return False, f"Ich kenne „{query.strip()}“ nicht. Scanne unter „Programme“ dein Startmenü, Master."
        if name not in self.allowed():
            return False, f"{name.title()} ist nicht freigegeben. Setze unter „Programme“ einen Haken, Master."
        try:
            self._start(self.all_apps()[name])
            return True, f"Ich öffne {name.title()}, Master."
        except Exception as e:
            return False, f"{name.title()} ließ sich nicht starten: {e}"

    @staticmethod
    def _start(target):
        if os.name != "nt":
            raise OSError("Programmstart funktioniert nur unter Windows")
        if os.path.exists(target) or "://" in target:
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=0x08000000)

    def scan(self):
        roots = [Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
                 Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
        found = {}
        for root in roots:
            if not root.exists():
                continue
            for lnk in root.rglob("*.lnk"):
                if _SKIP.search(lnk.stem):
                    continue
                found.setdefault(lnk.stem.lower(), str(lnk))
        self.settings.set("scanned_apps", found)
        return len(found)


def open_web(site, query=""):
    if query and site in SEARCH:
        from urllib.parse import quote_plus
        webbrowser.open(SEARCH[site] + quote_plus(query))
    else:
        webbrowser.open(WEB[site])
