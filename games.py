"""Spiele-Scanner: findet installierte Spiele von Steam, Epic und GOG."""
import json
import os
import re
from pathlib import Path

_SKIP = re.compile(r"steamworks|redistributable|proton|steam linux runtime|^steam$", re.I)


def parse_acf(text):
    """Steam-Manifest -> (appid, name) oder None."""
    a = re.search(r'"appid"\s+"(\d+)"', text)
    n = re.search(r'"name"\s+"([^"]+)"', text)
    if a and n and not _SKIP.search(n.group(1)):
        return a.group(1), n.group(1)
    return None


def parse_libraries(text):
    return [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', text)]


def parse_epic(text):
    """Epic-Manifest -> (Name, Startlink) oder None."""
    try:
        d = json.loads(text)
        name = d["DisplayName"]
        if d.get("MainGameAppName") and d["MainGameAppName"] != d["AppName"]:
            return None  # Zusatzinhalt
        link = (f"com.epicgames.launcher://apps/{d['CatalogNamespace']}%3A{d['CatalogItemId']}%3A{d['AppName']}"
                "?action=launch&silent=true")
        return name, link
    except Exception:
        return None


def _steam_root():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return Path(winreg.QueryValueEx(k, "SteamPath")[0])
    except Exception:
        for p in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
            if Path(p).exists():
                return Path(p)
    return None


def scan_steam():
    out = {}
    root = _steam_root()
    if not root:
        return out
    libs = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    try:
        libs += [Path(p) for p in parse_libraries(vdf.read_text(encoding="utf-8", errors="ignore"))]
    except Exception:
        pass
    for lib in libs:
        for f in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                r = parse_acf(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                r = None
            if r:
                out[r[1].lower()] = f"steam://rungameid/{r[0]}"
    return out


def scan_epic():
    out = {}
    d = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    for f in d.glob("*.item"):
        try:
            r = parse_epic(f.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            r = None
        if r:
            out[r[0].lower()] = r[1]
    return out


def scan_gog():
    out = {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games") as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                with winreg.OpenKey(root, winreg.EnumKey(root, i)) as k:
                    try:
                        name = winreg.QueryValueEx(k, "gameName")[0]
                        exe = winreg.QueryValueEx(k, "exe")[0]
                        out[name.lower()] = exe
                    except OSError:
                        pass
    except Exception:
        pass
    return out


def scan_all():
    games = {}
    for fn in (scan_gog, scan_epic, scan_steam):
        try:
            games.update(fn())
        except Exception:
            pass
    return games
