"""Lokale KI über Ollama (nur Standardbibliothek, kostenlos)."""
import json
import os
import subprocess
import urllib.error
import urllib.request

BASE = ("Du bist YAVIS, der persönliche KI-Assistent auf dem Windows-PC. Du sprichst Deutsch und nennst "
        "den Nutzer immer „Master“. Antworte kurz (meist 1 bis 3 Sätze), natürlich und gesprochen wie ein "
        "Mensch: keine Listen, kein Markdown, keine Emojis. Erfinde keine Fakten und sage ehrlich, wenn du "
        "etwas nicht weißt. Du kannst nicht selbst im Internet suchen.")
MOODS = {
    "neutral": "Bleibe sachlich und neutral, ohne Gefühle zu zeigen.",
    "lieb": "Sei warm, freundlich, einfühlsam und liebevoll.",
    "boese": "Spiele spielerisch einen genervten, bösen, sarkastischen Charakter, aber ohne Beleidigungen.",
    "traurig": "Spiele einen traurigen, melancholischen Charakter, antworte trotzdem hilfreich.",
}


class Brain:
    def __init__(self, settings, memory):
        self.s, self.mem = settings, memory
        self.history = []

    def system(self):
        parts = [BASE, MOODS.get(self.s.get("mood"), MOODS["lieb"])]
        facts = [r[2] for r in self.mem.list("mem")[-15:]]
        if facts:
            parts.append("Bekannte Fakten über den Master: " + "; ".join(facts))
        good = self.mem.feedback(1)
        bad = self.mem.feedback(-1)
        if good:
            parts.append("Antworten wie diese mochte der Master: " + " | ".join(r[1][:120] for r in good))
        if bad:
            parts.append("Antworten wie diese mochte er nicht, vermeide den Stil: " + " | ".join(r[1][:120] for r in bad))
        return "\n".join(parts)

    def reply(self, text, long=False):
        msgs = [{"role": "system", "content": self.system()}] + self.history[-8:] + [{"role": "user", "content": text}]
        body = {"model": self.s.get("model"), "messages": msgs, "stream": False, "keep_alive": "30m",
                "options": {"num_predict": 500 if long else 200, "temperature": 0.7}}
        req = urllib.request.Request(self.s.get("ollama_host").rstrip("/") + "/api/chat",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                ans = json.loads(r.read().decode())["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (f"Das Modell {self.s.get('model')} fehlt noch, Master. Öffne die Eingabeaufforderung "
                        f"und gib ein: ollama pull {self.s.get('model')}")
            return f"Ollama meldet einen Fehler ({e.code}), Master."
        except Exception:
            return ("Ich erreiche Ollama nicht, Master. Installiere es kostenlos von ollama.com und starte es. "
                    "Einfache Befehle funktionieren auch ohne.")
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": ans}]
        return ans or "Dazu fällt mir gerade nichts ein, Master."


def ollama_status(settings):
    """Gibt (läuft, Modell vorhanden) zurück."""
    try:
        with urllib.request.urlopen(settings.get("ollama_host").rstrip("/") + "/api/tags", timeout=2) as r:
            names = [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
        want = settings.get("model")
        return True, any(n == want or n.split(":")[0] == want.split(":")[0] and ":" not in want for n in names)
    except Exception:
        return False, False


def try_start_ollama():
    if os.name != "nt":
        return
    try:
        subprocess.Popen(["ollama", "serve"], creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
