"""Extras-Liste. kind 'cmd' = läuft ohne KI, 'ai' = braucht Ollama. ask = Eingabe nötig."""
E = []


def _c(cat, name, text, ask=None):
    E.append({"cat": cat, "name": name, "kind": "cmd", "text": text, "ask": ask})


def _a(cat, name, prompt, ask=None):
    E.append({"cat": cat, "name": name, "kind": "ai", "text": prompt, "ask": ask})


# Schnell, ohne KI
_c("Schnell", "Würfeln", "würfel")
_c("Schnell", "Münze werfen", "münze werfen")
_c("Schnell", "Zufallszahl 1–100", "zufallszahl von 1 bis 100")
_c("Schnell", "Passwort erzeugen", "passwort erzeugen")
_c("Schnell", "Uhrzeit", "uhrzeit")
_c("Schnell", "Datum", "datum")
_c("Schnell", "Systeminfo", "systeminfo")
_c("Schnell", "Zitat", "zitat")
# Organisation
_c("Organisation", "Timer", "timer {input}", "Wie lange? z. B. 5 minuten")
_c("Organisation", "Notiz speichern", "notiz {input}", "Was soll ich notieren?")
_c("Organisation", "Notizen anzeigen", "zeige notizen")
_c("Organisation", "Aufgabe eintragen", "aufgabe {input}", "Welche Aufgabe?")
_c("Organisation", "Aufgaben anzeigen", "zeige aufgaben")
# Windows
for n, w in (("Rechner", "rechner"), ("Editor", "editor"), ("Explorer", "explorer"),
             ("Task-Manager", "task-manager"), ("Einstellungen", "einstellungen"),
             ("Snipping-Tool", "snipping-tool")):
    _c("Windows", n + " öffnen", "öffne " + w)
# Web
_c("Web", "YouTube öffnen", "youtube")
_c("Web", "YouTube suchen", "youtube {input}", "Wonach suchen?")
_c("Web", "Google-Suche", "google {input}", "Wonach suchen?")
_c("Web", "Spotify öffnen", "spotify")
_c("Web", "Preisvergleich (Google)", "google preis {input}", "Für welches Produkt?")
# Stimmung
_c("Stimmung", "Lieb sein", "sei lieb")
_c("Stimmung", "Böse sein", "sei böse")
_c("Stimmung", "Traurig sein", "sei traurig")
_c("Stimmung", "Neutral sein", "sei neutral")
# KI: Spaß & Alltag
_a("Spaß & Alltag", "Witz", "Erzähl mir einen kurzen, guten Witz.")
_a("Spaß & Alltag", "Rätsel", "Stelle mir ein kurzes Rätsel, ohne die Lösung zu verraten.")
_a("Spaß & Alltag", "Rap", "Rappe vier Zeilen über {input}.", "Thema?")
_a("Spaß & Alltag", "Gedicht", "Schreibe ein kurzes Gedicht über {input}.", "Thema?")
_a("Spaß & Alltag", "Gute-Nacht-Geschichte", "Erzähle eine kurze, beruhigende Gute-Nacht-Geschichte.")
_a("Spaß & Alltag", "Fakt des Tages", "Nenne einen überraschenden, wahren Fakt.")
_a("Spaß & Alltag", "Rezeptidee", "Schlage ein einfaches Rezept mit {input} vor.", "Welche Zutaten?")
_a("Spaß & Alltag", "Workout-Idee", "Gib mir ein kurzes 15-Minuten-Workout ohne Geräte.")
_a("Spaß & Alltag", "Motivation", "Motiviere mich in zwei Sätzen.")
_a("Spaß & Alltag", "Ausrede-Generator", "Erfinde eine lustige, harmlose Ausrede, warum ich zu spät bin.")
_a("Spaß & Alltag", "Spitzname-Generator", "Gib mir drei coole Spitznamen für {input}.", "Für wen?")
# KI: Lernen & Reisen
_a("Lernen", "Reiseplan", "Plane kurz einen Tagesausflug nach {input}.", "Wohin?")
_a("Lernen", "Lernplan", "Erstelle einen kurzen Lernplan für {input}.", "Was möchtest du lernen?")
_a("Lernen", "Übersetzer", "Übersetze ins Englische: {input}", "Welcher Text?")
_a("Lernen", "Code-Hilfe", "Hilf mir bei diesem Programmierproblem, kurz: {input}", "Problem?")
# KI: Arbeit
_a("Arbeit", "Tagesplan", "Erstelle mir einen kurzen Tagesplan für heute. Aufgaben: {input}", "Deine Aufgaben?")
_a("Arbeit", "E-Mail-Entwurf", "Schreibe einen kurzen, höflichen E-Mail-Entwurf zu: {input}", "Worum geht es?")
_a("Arbeit", "Angebot-Entwurf", "Entwirf ein kurzes Angebot für: {input}", "Für welche Leistung?")
_a("Arbeit", "Produktbeschreibung", "Schreibe eine verkaufsstarke Produktbeschreibung für: {input}", "Welches Produkt?")
_a("Arbeit", "Geschäftsidee prüfen", "Prüfe diese Geschäftsidee ehrlich auf Chancen und Risiken: {input}", "Deine Idee?")
