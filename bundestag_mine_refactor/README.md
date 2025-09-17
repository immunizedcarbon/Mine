# Bundestags-Mine Refactor (Python 2025)

Diese Codebasis bildet den modernen Kern der Bundestags-Mine Pipeline in Python.
Sie ersetzt die ursprünglichen .NET- und Java-Komponenten durch ein schlankes
Setup, das alle Verarbeitungsschritte – Datenabruf, Parsing, Persistenz und
KI-Auswertung – aus einer Hand übernimmt.

## Ziele

* Zugriff auf den Bundestags-Datenservice (DIP) ausschließlich per offizieller
  REST-API.
* Zerlegung der Plenarprotokolle in strukturierte Redebeiträge.
* Persistente Speicherung in einer lokalen SQLite-Datenbank ohne zusätzliche
  Token- oder Statistiktabellen.
* KI-gestützte Zusammenfassungen jeder Rede über die Gemini 2.5 Pro API.

## Projektstruktur

```
bundestag_mine_refactor/
├── bundestag_mine_refactor/
│   ├── cli.py              # Kommandozeilen-Einstieg
│   ├── config.py           # Konfiguration (Datei + Umgebungsvariablen)
│   ├── dip_client.py       # Zugriff auf die DIP REST-API
│   ├── models.py           # SQLAlchemy-ORM-Modelle
│   ├── parser.py           # Zerlegung von Protokollen in Reden
│   ├── pipeline.py         # Orchestrierung Import + Summaries
│   ├── storage.py          # SQLite Persistence Layer
│   ├── summarizer.py       # Gemini 2.5 Pro Integration
│   ├── types.py            # Domänen-Dataclasses
│   └── __main__.py         # `python -m bundestag_mine_refactor`
├── pyproject.toml          # Projekt-Metadaten & Abhängigkeiten
└── tests/                  # Pytest-basierte Einheiten-Tests
```

## Installation

```bash
cd bundestag_mine_refactor
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Konfiguration

Die Anwendung liest Konfigurationen aus einer optionalen JSON-Datei
(`bundestag_mine_refactor.json` im Projektroot oder `~/.config/bundestag_mine_refactor/config.json`)
und aus Umgebungsvariablen mit dem Präfix `BMR_`.

Wichtige Variablen:

* `BMR_DIP_API_KEY` – Schlüssel für die DIP-API.
* `BMR_STORAGE_DATABASE_URL` – Pfad zur SQLite-Datei (Standard: `sqlite:///bundestag_mine.db`).
* `BMR_GEMINI_API_KEY` – Schlüssel für die Gemini 2.5 Pro API.
* `BMR_GEMINI_MODEL` – Modellname (Standard `gemini-2.5-pro`).

## Nutzung

Protokolle importieren und direkt zusammenfassen:

```bash
bundestag-mine-refactor import --limit 5
```

Nur neue Protokolle seit einem Timestamp laden:

```bash
bundestag-mine-refactor import --since 2024-05-01T00:00:00
```

Summaries deaktivieren (z. B. bei fehlendem API-Key):

```bash
bundestag-mine-refactor import --without-summaries
```

Die Pipeline erzeugt eine SQLite-Datenbank `bundestag_mine.db`, in der
Plenarprotokolle (`protocols`) und Reden (`speeches`) inklusive KI-Output
abgelegt werden.

## Tests

```bash
pytest
```

Die enthaltenen Tests prüfen u. a. das Parsing deutscher Protokolle und die
Interpretation der DIP-Metadaten.

## Ausblick

* Ergänzung einer HTML-Report-Generierung für lokale Auswertungen.
* Erweiterte KI-Aufrufe (Sentiment, Topics) über optionale Prompts.
* Zusätzliche Qualitätschecks für sehr große Reden (Chunking-Strategie).
