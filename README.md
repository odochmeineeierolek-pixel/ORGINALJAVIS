# YAVIS – persönlicher KI-Assistent für Windows 11

Kostenlos, lokal, ohne CMD. Rot-Schwarz-Gelbe Oberfläche mit pulsierendem Kreis.

## EXE bekommen (nur Download nötig)
1. Alle Dateien dieses Ordners in ein GitHub-Repository hochladen (auch den Ordner `.github`).
2. Tab **Actions** → „Build YAVIS-Setup“ abwarten (grüner Haken).
3. Unten unter **Artifacts** `YAVIS-Setup` herunterladen, entpacken, `YAVIS-Setup.exe` ausführen.

## Einmalig für die KI
Ollama von ollama.com installieren, dann in der Eingabeaufforderung: `ollama pull llama3.2:3b`.
Einfache Befehle (Programme, Uhrzeit, Würfeln, Rechnen, Timer …) laufen auch ohne Ollama.

## Bedienung
- „Hey Yavis, öffne YouTube“ – Taste „Dauerhaft zuhören“ aktivieren, oder 🎤 für eine einzelne Frage.
- Stimmen: Menü „Stimmen“ (Vorschau, Auswahl, Tempo, Tonhöhe, Lautstärke, Download).
- Aktivierungsnamen, Stimmung und Mikrofon: **Einstellungen**.
- Welche Programme gestartet werden dürfen: **Programme** (Haken setzen, Startmenü scannen).
- Spiele: werden beim Start automatisch gescannt (Steam, Epic, GOG). „Starte mein Spiel Minecraft“ startet es. Weitere über „Startmenü scannen“.
- Musik aus eigenem Ordner: **Musik**. Weitere Funktionen: **Extras**.
- „Sei neutral“ schaltet die Gefühle aus.

## Ehrliche Einschränkungen
- Stimmen: 45 Profile auf Basis von 6 echten Piper-Sprechern (Eva, Kerstin, Ramona, Karlsson, Pavoque, Thorsten, dazu Thorsten mit Gefühlen). Die Profile unterscheiden sich in Tonhöhe, Tempo und Lautstärke, es sind keine 45 verschiedenen Menschen. Beim ersten Benutzen lädt YAVIS Engine und Stimme (Menü „Stimmen“). Die Lizenzen der einzelnen Stimmen stehen in deren MODEL_CARD auf huggingface.co/rhasspy/piper-voices – vor kommerzieller Nutzung prüfen.
- Beim ersten Zuhören lädt faster-whisper einmalig sein Modell (Internet nötig).
- Kein selbstständiges Geldverdienen; Verkaufen, Bezahlen, Senden nur durch dich.
- Daten liegen lokal in `%APPDATA%\YAVIS`.
