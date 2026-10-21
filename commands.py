"""Schnelle Befehle ohne KI (Uhrzeit, Programme, Würfeln, Rechnen ...)."""
import ast
import operator
import os
import platform
import random
import re
import secrets
import shutil
import string
from datetime import datetime

from .apps import WEB, open_web

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]
QUOTES = [
    "Der beste Zeitpunkt anzufangen war gestern, der zweitbeste ist jetzt.",
    "Kleine Schritte jeden Tag schlagen große Pläne ohne Start.",
    "Fehler sind der Beweis, dass du es versuchst.",
    "Disziplin ist die Brücke zwischen Zielen und Ergebnissen.",
    "Wer aufhört besser zu werden, hat aufgehört gut zu sein.",
    "Mut heißt nicht, keine Angst zu haben, sondern trotzdem loszugehen.",
    "Was du heute vorbereitest, dankt dir morgen.",
]
MOOD_WORDS = {"neutral": "neutral", "lieb": "lieb", "nett": "lieb", "freundlich": "lieb",
              "böse": "boese", "wütend": "boese", "traurig": "traurig"}


# ---------------- Aktivierungswörter ----------------
def _variants(name):
    name = name.lower().strip()
    out = {name}
    for a, b in (("y", "j"), ("j", "y"), ("v", "w"), ("w", "v")):
        out |= {v.replace(a, b) for v in list(out)}
    return out


def strip_wake(text, names):
    """Gibt (aktiviert, Rest) zurück. 'Hallo' allein aktiviert ebenfalls."""
    allv = set()
    for n in names:
        if n.strip():
            allv |= _variants(n)
    pre = r"(?:(?:hallo|hey|hi|ok|okay|na)\W+)?"
    if allv:
        alt = "|".join(re.escape(v) for v in sorted(allv, key=len, reverse=True))
        m = re.match(rf"^\W*{pre}(?:{alt})\b[\s,.:!?\-]*(.*)$", text.strip(), re.I | re.S)
        if m:
            return True, m.group(1).strip()
    if re.match(r"^\W*(hallo|hey|hi)\W*$", text.strip(), re.I):
        return True, ""
    return False, text


# ---------------- sicherer Taschenrechner ----------------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}


def safe_calc(expr):
    expr = expr.lower()
    for a, b in ((" geteilt durch ", "/"), (" mal ", "*"), (" plus ", "+"), (" minus ", "-"),
                 ("^", "**"), ("x", "*"), (",", ".")):
        expr = expr.replace(a, b)
    expr = expr.strip(" ?=")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 100:
                raise ValueError("Exponent zu groß")
            return _OPS[type(n.op)](a, b)
        raise ValueError("Ungültiger Ausdruck")

    return ev(ast.parse(expr, mode="eval"))


def _fmt(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:.6g}" if isinstance(v, float) else str(v)


# ---------------- Hauptfunktion ----------------
def handle(text, ctx):
    """Gibt eine Antwort zurück oder None, wenn die KI antworten soll."""
    t = text.strip()
    low = t.lower().strip(" .!?")
    if not low:
        return None

    m = re.search(r"\bsei\s+(?:jetzt\s+|wieder\s+|bitte\s+)*(neutral|lieb|nett|freundlich|böse|wütend|traurig)\b", low)
    if m:
        mood = MOOD_WORDS[m.group(1)]
        ctx.set_mood(mood)
        return {"neutral": "Verstanden, ich bleibe sachlich und neutral, Master.",
                "lieb": "Sehr gern, Master. Ich bin ganz lieb zu dir.",
                "boese": "Na gut, Master. Dann bin ich jetzt mal richtig grummelig.",
                "traurig": "Okay, Master... ich bin jetzt ein bisschen traurig."}[mood]

    if re.search(r"wie spät|uhrzeit|wie viel uhr|wieviel uhr", low):
        return f"Es ist {datetime.now():%H:%M} Uhr, Master."
    if re.search(r"\b(datum|welcher tag|welchen tag|welches datum)\b", low):
        d = datetime.now()
        return f"Heute ist {WEEKDAYS[d.weekday()]}, der {d.day}. {MONTHS[d.month - 1]} {d.year}, Master."

    m = re.match(r"^(?:merk|merke)\s+dir\s+(?:dass\s+)?(.+)$", t, re.I)
    if m:
        ctx.memory.add("mem", m.group(1))
        return "Gemerkt, Master."
    if re.search(r"was weißt du (über mich|von mir)|zeige? (mir )?(dein )?gedächtnis|was hast du dir gemerkt", low):
        rows = ctx.memory.list("mem")
        if not rows:
            return "Ich habe mir noch nichts gemerkt, Master."
        return "Ich weiß: " + "; ".join(r[2] for r in rows[-8:]) + "."
    if re.search(r"vergiss (alles|alle)", low):
        return "Löschen musst du selbst bestätigen, Master: Einstellungen, dann Gedächtnis."

    m = re.match(r"^notiz\s+(.+)$", t, re.I)
    if m:
        ctx.memory.add("note", m.group(1))
        return "Notiz gespeichert, Master."
    m = re.match(r"^aufgabe\s+(.+)$", t, re.I)
    if m:
        ctx.memory.add("task", m.group(1))
        return "Aufgabe eingetragen, Master."
    if re.search(r"(zeige?|lies|nenn)\w*\s+(mir\s+)?(meine\s+)?notizen|^notizen$", low):
        rows = ctx.memory.list("note")
        return ("Deine Notizen: " + "; ".join(r[2] for r in rows[-8:]) + ".") if rows else "Du hast keine Notizen, Master."
    if re.search(r"(zeige?|lies|nenn)\w*\s+(mir\s+)?(meine\s+)?aufgaben|^aufgaben$|offene aufgaben", low):
        rows = ctx.memory.list("task")
        return ("Deine Aufgaben: " + "; ".join(r[2] for r in rows[-8:]) + ".") if rows else "Keine offenen Aufgaben, Master."

    if "würfel" in low:
        m = re.search(r"w(\d+)", low)
        sides = min(int(m.group(1)), 1000) if m and int(m.group(1)) > 1 else 6
        return f"Ich habe eine {random.randint(1, sides)} gewürfelt, Master."
    if re.search(r"münze|kopf oder zahl", low):
        return f"{random.choice(['Kopf', 'Zahl'])}, Master."
    if "zufallszahl" in low:
        m = re.search(r"(\d+)\s*bis\s*(\d+)", low)
        a, b = (int(m.group(1)), int(m.group(2))) if m else (1, 100)
        if a > b:
            a, b = b, a
        return f"Deine Zufallszahl ist {random.randint(a, b)}, Master."
    if "passwort" in low and re.search(r"erzeug|generier|erstell|neues", low):
        pw = "".join(secrets.choice(string.ascii_letters + string.digits + "!$%&?#") for _ in range(16))
        ctx.clipboard(pw)
        return "Ich habe ein sicheres Passwort erzeugt und in die Zwischenablage kopiert, Master."
    if "zitat" in low:
        return random.choice(QUOTES)
    if re.search(r"\bsysteminfo|systeminformation", low):
        free = shutil.disk_usage(os.path.abspath(os.sep)).free // 2**30
        return (f"System: {platform.system()} {platform.release()}, {os.cpu_count()} Prozessorkerne, "
                f"{free} Gigabyte frei auf dem Laufwerk, Master.")

    m = re.search(r"timer\s+(?:für\s+|auf\s+)?(\d+)\s*(sekunde|sek|minute|min|stunde|std)", low)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        secs = n * (3600 if unit.startswith(("stunde", "std")) else 60 if unit.startswith("min") else 1)
        ctx.timer(secs, f"{n} {unit}")
        return f"Timer für {n} {unit} läuft, Master."

    expr = None
    m = re.match(r"^(?:rechne|berechne|was ist|wie viel ist|wieviel ist)\s+(.+)$", low)
    if m:
        expr = m.group(1)
    elif re.fullmatch(r"[\d\s+\-*/().,x^%]+", low) and re.search(r"[+\-*/x^%]", low):
        expr = low
    if expr and re.search(r"\d", expr):
        try:
            return f"{expr.strip()} ergibt {_fmt(safe_calc(expr))}, Master."
        except ZeroDivisionError:
            return "Durch null kann ich nicht teilen, Master."
        except Exception:
            if m and re.match(r"^(?:was ist|wie viel ist|wieviel ist)", low):
                pass  # keine Rechenaufgabe -> KI
            else:
                return "Das konnte ich nicht ausrechnen, Master."

    for site in WEB:
        if re.search(rf"\b{site}\b", low):
            q = re.sub(rf"^.*?\b{site}\b", "", low, count=1)
            q = re.sub(r"^\s*(und|auf|bei|nach|suche|such|öffne|starte|mir|mal|bitte|eine|ein|zeig|spiele|spiel|:)\b", "", q).strip(" ,.:")
            q = re.sub(r"^(nach|für)\s+", "", q).strip()
            open_web(site, q)
            return f"Ich öffne {site.title()}" + (f" und suche nach {q}" if q and site in ("youtube", "google", "spotify", "wikipedia") else "") + ", Master."

    m = re.match(r"^(?:suche|such|google)\s+(?:nach\s+)?(.+)$", low)
    if m:
        open_web("google", m.group(1))
        return f"Ich suche nach {m.group(1)}, Master."

    if re.fullmatch(r"(?:starte|öffne|spiele|zocke)\s+(?:mein(?:e|en)?\s+)?(?:spiel|game|spiele)", low):
        names = sorted(ctx.apps.games())[:6]
        if names:
            return "Welches Spiel, Master? Ich kenne zum Beispiel " + ", ".join(n.title() for n in names) + "."
        return "Ich kenne noch keine Spiele, Master. Drück unter „Programme“ auf „Spiele scannen“."
    m = re.match(r"^(?:spiele|zocke|zock)\s+(.+)$", low)
    if m:
        name = ctx.apps.find(m.group(1))
        if name and name in ctx.apps.games():
            return ctx.apps.launch(name)[1]

    m = re.match(r"^(?:öffne|öffnen|starte|starten|start|mach auf|open)\s+(.+)$", low)
    if m:
        return ctx.apps.launch(m.group(1))[1]

    if re.fullmatch(r"(hallo|hey|hi)( yavis| jarvis)?", low):
        return "Hallo Master, wie kann ich dir helfen?"
    return None
