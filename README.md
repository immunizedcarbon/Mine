# Bundestag Mine Refactor

Eine modernisierte, modular aufgebaute Pipeline zum Herunterladen, Parsen, Persistieren und optionalen Zusammenfassen von Plenarprotokollen des Deutschen Bundestags.

## Inhalt

- [Überblick](#überblick)
- [Projektstruktur](#projektstruktur)
- [Systemvoraussetzungen](#systemvoraussetzungen)
- [Installation auf Kubuntu 24.04](#installation-auf-kubuntu-2404)
- [Konfiguration](#konfiguration)
- [Schnellstart](#schnellstart)
- [Grafische Oberfläche](#grafische-oberfläche)
- [Tests & Qualitätssicherung](#tests--qualitätssicherung)
- [Datenhaltung](#datenhaltung)
- [Weiterführende Informationen](#weiterführende-informationen)
- [Fehlerbehebung](#fehlerbehebung)

## Überblick

Die Anwendung holt Sitzungsprotokolle über das offizielle DIP-API des Bundestags ab, zerlegt sie in einzelne Redebeiträge, speichert die Inhalte in einer relationalen Datenbank und erstellt auf Wunsch Kurzfassungen über die Gemini 2.5 Pro API. Sämtliche Komponenten sind in klar abgegrenzte Python-Module gegliedert und lassen sich unabhängig voneinander testen.

## Projektstruktur

```
.
├── docs/                     # Ergänzende Dokumentation (z. B. Architektur)
├── pyproject.toml            # Projektmetadaten & Abhängigkeiten
├── requirements.txt          # Minimale Laufzeit-Abhängigkeiten
├── src/
│   └── bundestag_mine_refactor/
│       ├── __init__.py       # Öffentliche API des Pakets
│       ├── __main__.py       # Einstiegspunkt für `python -m ...`
│       ├── cli.py            # Kommandozeileninterface
│       ├── clients/          # HTTP-Clients (v. a. DIP)
│       ├── config/           # Konfigurationsmodelle & Laderoutinen
│       ├── core/             # Domänenobjekte (Protokolle, Reden)
│       ├── database/         # SQLAlchemy-Modelle & Storage-Fassade
│       ├── parsing/          # Parser für Plenarprotokolle
│       ├── pipeline/         # Orchestrierung des ETL-Prozesses
│       └── summarization/    # Anbindung an Generative-AI-Dienste
└── tests/
    ├── clients/              # Unit-Tests für API-Clients
    └── parsing/              # Unit-Tests für Parser
```

Ein detaillierter Architekturüberblick findet sich unter [`docs/architecture.md`](docs/architecture.md).

## Systemvoraussetzungen

- Kubuntu 24.04 (oder kompatibles Ubuntu 24.04 Derivat)
- Python ≥ 3.10 (empfohlen: das systemseitige Python 3.12)
- Git
- Optional: Zugangsdaten für das [DIP-API](https://dip.bundestag.de) und einen Gemini 2.5 Pro API Key

## Installation auf Kubuntu 24.04

Die folgenden Schritte lassen sich in einem Terminal 1:1 kopieren.

1. **Systempakete aktualisieren und Laufzeit-Abhängigkeiten installieren**

   ```bash
   sudo apt update
   sudo apt install -y python3.12 python3.12-venv python3-pip git build-essential
   ```

2. **Repository klonen und in das Projektverzeichnis wechseln**

   ```bash
   git clone https://github.com/<ihr-account>/bundestag-mine-refactor.git
   cd bundestag-mine-refactor
   ```

3. **Virtuelle Umgebung anlegen und aktivieren**

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

4. **Pip aktualisieren und Projekt installieren**

   ```bash
   python -m pip install --upgrade pip
   pip install -e .
   ```

   Für Entwicklung inklusive Test-Werkzeugen kann alternativ installiert werden:

   ```bash
   pip install -e .[dev]
   ```

5. **(Optional) Minimale Abhängigkeiten ohne Virtualenv installieren** – falls das Projekt in einem Container oder CI-System läuft, genügt `pip install .`.

## Konfiguration

Die Anwendung verwendet dreistufige Konfigurationen: Standardwerte, optionale JSON-Dateien sowie Umgebungsvariablen mit dem Präfix `BMR_`.

### Konfigurationsdatei

Erstellen Sie optional eine Datei `bundestag_mine_refactor.json` im Projektverzeichnis oder unter `~/.config/bundestag_mine_refactor/config.json`. Beispiel:

```json
{
  "dip": {
    "api_key": "DIP-API-KEY",
    "page_size": 50
  },
  "gemini": {
    "api_key": "GEMINI-API-KEY",
    "model": "gemini-2.5-pro"
  },
  "storage": {
    "database_url": "sqlite:///bundestag_mine.db"
  }
}
```

### Umgebungsvariablen

| Variable             | Bedeutung                                      |
|----------------------|------------------------------------------------|
| `BMR_DIP_API_KEY`    | API-Key für das DIP-Portal                      |
| `BMR_DIP_BASE_URL`   | Alternative Basis-URL des DIP-API               |
| `BMR_GEMINI_API_KEY` | API-Key für Gemini 2.5 Pro                      |
| `BMR_GEMINI_ENABLE_SAFETY_SETTINGS` | `true` aktiviert die Safety-Filter (Standard: aus) |
| `BMR_STORAGE_DATABASE_URL` | Vollständige SQLAlchemy-URL zur Datenbank |
| `BMR_STORAGE_ECHO_SQL`     | `true`/`false` für SQL-Debug-Ausgaben      |

Umgebungsvariablen überschreiben Werte aus der Konfigurationsdatei. Bei Bedarf kann per CLI-Flag `--config` eine spezifische JSON-Datei geladen werden.

## Schnellstart

1. **Kommandozeilenwerkzeug verwenden**

   ```bash
   bundestag-mine-refactor import --since 2024-01-01T00:00:00 --limit 5
   ```

   - `--since` filtert Protokolle nach Aktualisierungsdatum (ISO-8601).
   - `--limit` begrenzt die Anzahl der verarbeiteten Protokolle.
   - `--without-summaries` deaktiviert Gemini-Zusammenfassungen, selbst wenn ein API-Key konfiguriert ist.

2. **Modul direkt starten**

   ```bash
   python -m bundestag_mine_refactor import --limit 1
   ```

3. **Programmatische Nutzung**

   ```python
   from bundestag_mine_refactor import ImportPipeline, clients, config, database, summarization

   app_config = config.load_config()
   dip_client = clients.DIPClient(app_config.dip.base_url, app_config.dip.api_key)
   storage = database.create_storage(app_config.storage.database_url)
   pipeline = ImportPipeline(dip_client=dip_client, storage=storage)
   pipeline.run(limit=1)
   ```

4. **Grafische Oberfläche starten**

   ```bash
   bundestag-mine-refactor ui --ui-host 0.0.0.0 --ui-port 8080
   ```

   - Moderne Single-Page-Oberfläche auf Basis von NiceGUI.
   - Echtzeit-Status, Logstream und abrufbare Datenbank-Snapshots.
   - Import-Läufe lassen sich komfortabel starten, überwachen und abbrechen.

## Grafische Oberfläche

Die UI ist als responsive Control-Center umgesetzt. Sie bündelt alle relevanten Steuerungsmöglichkeiten in einer modernen Weboberfläche und läuft komplett in Python. Wichtige Merkmale:

- **Live-Monitoring:** Fortschritt, Anzahl gespeicherter Reden und erzeugter Zusammenfassungen werden in Echtzeit aktualisiert.
- **Streaming-Log:** Jede Pipeline-Phase erscheint im Log inklusive Protokoll-ID und Titel.
- **Abbruch & Wiederaufnahme:** Langlaufende Imports können per Klick abgebrochen werden, ein erneuter Start ist jederzeit möglich.
- **Persistenz-Explorer:** Eine Tabelle zeigt die zuletzt importierten Protokolle inklusive Sitzung, Datum und Redenzahl.
- **Konfigurationsübersicht:** API-Endpunkte, Datenbankziel und Gemini-Status sind transparent im Interface sichtbar.

Standardmäßig bindet der Server an `127.0.0.1:8080`. Über `--ui-host` und `--ui-port` lässt sich dies anpassen (z. B. `--ui-host 0.0.0.0`, um die UI im Netzwerk erreichbar zu machen). Beim Schließen des Prozesses wird der Hintergrundthread sauber beendet und der HTTP-Client freigegeben.

## Tests & Qualitätssicherung

Alle Unit-Tests laufen mit `pytest`.

```bash
source .venv/bin/activate  # falls noch nicht aktiv
pip install -e .[dev]
pytest
```

Weitere Empfehlungen:

- `python -m pip list --outdated` zur Pflege der Abhängigkeiten.
- Datenbank-Migrationen sollten über SQLAlchemy Alembic erfolgen (nicht enthalten, kann aber leicht ergänzt werden).

## Datenhaltung

- Standardmäßig wird eine SQLite-Datenbank `bundestag_mine.db` im Projektverzeichnis verwendet.
- Der Speicherlayer (`database.Storage`) abstrahiert sämtliche SQLAlchemy-Operationen und ermöglicht den Austausch der Datenbank, indem `storage.database_url` angepasst wird (z. B. `postgresql+psycopg://user:pass@host/db`).
- Reden, für die noch keine Zusammenfassung vorhanden ist, können über `storage.pending_summaries()` ermittelt und anschließend mit `storage.update_summary()` aktualisiert werden.

## Weiterführende Informationen

- [Architekturüberblick](docs/architecture.md)
- Offizielle APIs:
  - [DIP Dokumentationsportal](https://dip.bundestag.de)
  - [Google AI Studio – Gemini 2.5 Pro](https://ai.google.dev/)

## Fehlerbehebung

| Problem                                  | Lösungsvorschlag |
|------------------------------------------|------------------|
| `ModuleNotFoundError` nach Installation  | Prüfen, ob die virtuelle Umgebung aktiviert ist (`source .venv/bin/activate`). |
| Netzwerkfehler beim DIP-Abruf            | Retry-Anzahl (`dip.max_retries`) erhöhen oder Verbindung prüfen. |
| Gemini-Zusammenfassungen werden übersprungen | Sicherstellen, dass `BMR_GEMINI_API_KEY` gesetzt oder in der Konfigurationsdatei hinterlegt ist und `--without-summaries` nicht gesetzt wurde. |
| SQLite-Datei gesperrt                    | Offene Prozesse schließen oder auf eine externe Datenbank ausweichen. |

Für weitergehende Fragen oder Beiträge nutzen Sie bitte Pull Requests oder Issues im Repository.
