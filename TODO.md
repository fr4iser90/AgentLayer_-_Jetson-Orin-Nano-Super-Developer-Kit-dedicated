Add llama.cpp

integrate PIDEA api ( needs to be done in PIDEA project)

🧠 Beste Praxis (wichtig!)
1. LLM darf NICHT direkt Rohdaten interpretieren

Stattdessen:

👉 Step 1: Tool/Code layer (deterministisch)

parse calendar
berechne Dauer
filtere relevante Events (z. B. “nächster Dienst”)

👉 Step 2: LLM bekommt nur clean structured summary

Beispiel:

{
  "next_shift": {
    "date": "2026-04-27",
    "start": "05:35",
    "end": "13:50",
    "duration_minutes": 495
  }
}

Dann darf das LLM nur noch sagen:

„Du arbeitest wieder am 27.04. von 05:35 bis 13:50.“

🚫 Was du NICHT machen solltest

❌ Roh ICS / Kalendertext direkt ins Prompt
❌ “Hier sind deine Termine:” + dump
❌ freie Interpretation erlauben
❌ Zeitberechnungen im LLM

⚡ Bessere Architektur (sehr empfohlen)
🔹 Option A: Clean Tool Output (Best Practice)
calendar.getNextShift() → structured JSON

LLM Prompt:

„Du bekommst ein JSON mit dem nächsten Dienst. Antworte kurz.“

🔹 Option B: Hybrid (wenn du mehr Kontext willst)
Tool liefert:
nächste Schicht
heute frei/arbeit
ggf. Hinweis „Feiertag irrelevant“
LLM macht nur Sprachform
🔹 Option C: Hard Guardrails

Wenn du beim LLM bleibst:

temperature = 0
“verändere keine Zahlen”
“kopiere Daten exakt”

Aber ehrlich: das reicht oft NICHT zuverlässig.