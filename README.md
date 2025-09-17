# Mine – Pipeline für Bundestagsprotokolle

Mine lädt Plenarprotokolle aus dem Dokumentations- und Informationssystem des Deutschen Bundestags (DIP), zerlegt die Texte in Redebeiträge und speichert alles in einer relationalen Datenbank. Optional fasst die Anwendung Reden mit Googles Gemini-API zusammen und bietet eine NiceGUI-Oberfläche zum Steuern der Pipeline.

## Funktionsüberblick

- **Robuster Import**: `DIPClient` holt Metadaten und Volltexte, setzt Cursors korrekt ein und wiederholt fehlgeschlagene HTTP-Anfragen.
- **Parser für Reden**: `parse_speeches` entfernt Regieanweisungen, erkennt Sprecher*innen sowie Parteien und liefert strukturierte `Speech`-Objekte.
- **Speicherung mit SQLAlchemy**: `Storage` verwaltet ein SQLite-Standard-Schema und unterstützt alternative SQLAlchemy-URLs.
- **Optionale Zusammenfassungen**: `GeminiSummarizer` generiert Kurzfassungen, wenn ein Gemini-API-Schlüssel hinterlegt ist.
- **NiceGUI Control Center**: Über `mine ui` lassen sich Importe starten/stoppen, Logs einsehen, Summaries überwachen und Einstellungen pflegen.
- **CLI-Automatisierung**: `mine import` verarbeitet Protokolle skriptgesteuert, inklusive Limit- und Zeitfilter.

## Voraussetzungen (getestet mit Kubuntu 24.04)

- Python ≥ 3.10 (Kubuntu 24.04 bringt Python 3.12 mit).
- `python3-venv`, `git` sowie Build-Werkzeuge (`build-essential`).
- Optional: DIP-API-Schlüssel und Google Gemini API Key.

## Schnellstart

### Komplettinstallation *und* Start (frisches System)

```bash
sudo apt update \
  && sudo apt install -y python3.12 python3.12-venv python3-pip git build-essential \
  && git clone https://github.com/immunizedcarbon/Mine.git \
  && cd Mine \
  && python3.12 -m venv .venv \
  && source .venv/bin/activate \
  && python -m pip install --upgrade pip \
  && pip install -e . \
  && mine ui
```

### Nur starten (Projekt bereits geklont & installiert)

```bash
cd Mine && source .venv/bin/activate && mine ui
```

Die NiceGUI-Oberfläche läuft anschließend unter <http://127.0.0.1:8080>. Beende sie mit `Ctrl+C`.

## Manuelle Installation

1. Repository klonen und wechseln:
   ```bash
   git clone https://github.com/immunizedcarbon/Mine.git
   cd Mine
   ```
2. Virtuelle Umgebung einrichten:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Abhängigkeiten installieren:
   ```bash
   python -m pip install --upgrade pip
   pip install -e .
   ```
4. (Optional) Entwicklungs- und Testwerkzeuge:
   ```bash
   pip install -e .[dev]
   ```

## Konfiguration

`mine` verwendet ohne weitere Angaben eine SQLite-Datei `mine.db` im Projektordner. Konfigurationen werden als JSON gespeichert – standardmäßig unter `~/.config/mine/config.json`. Lade oder überschreibe Einstellungen über:

- `--config /pfad/zur/config.json` bei CLI-Aufrufen.
- NiceGUI: Tab „Konfiguration“ → „Speichern“ legt die Datei an.
- Umgebungsvariablen im Format `MINE_<BEREICH>_<FELD>`, z. B. `MINE_DIP_API_KEY`, `MINE_STORAGE_DATABASE_URL`.

Wichtige Optionen:

| Bereich | Schlüssel | Bedeutung |
| --- | --- | --- |
| `dip.base_url` | Basis-URL der DIP-API (Default: `https://search.dip.bundestag.de/api/v1`). |
| `dip.api_key` | Optionaler API-Schlüssel für höhere Abruflimits. |
| `gemini.api_key` | Aktiviert Zusammenfassungen; ohne Schlüssel werden Summaries übersprungen. |
| `storage.database_url` | SQLAlchemy-Verbindungszeichenkette, z. B. `sqlite:///mine.db` oder `postgresql+psycopg://…`. |

## Nutzung

### CLI

Nach Aktivieren der virtuellen Umgebung steht das Skript `mine` bereit.

- **Import starten**:
  ```bash
  mine import --since 2024-01-01T00:00:00 --limit 10
  ```
  Wichtige Optionen: `--config`, `--since`, `--limit`, `--without-summaries`.
- **UI starten**:
  ```bash
  mine ui --ui-host 0.0.0.0 --ui-port 8080
  ```

### NiceGUI-Oberfläche

- Start/Stopp der Pipeline.
- Live-Log, letzte Protokolle, Laufzeitstatistiken.
- Formular zum Bearbeiten der DIP-, Gemini- und Datenbank-Einstellungen.
- Speichert Konfigurationsänderungen auf Wunsch in der JSON-Datei.

### Programmatisch

```python
from mine import ImportPipeline, clients, config, database

app_config = config.load_config()
dip_client = clients.DIPClient(app_config.dip.base_url, app_config.dip.api_key)
storage = database.create_storage(app_config.storage.database_url)
pipeline = ImportPipeline(dip_client=dip_client, storage=storage)
pipeline.run(limit=1)
```

## Datenhaltung

- Standardmäßig wird `sqlite:///mine.db` genutzt; Tabellen werden automatisch erzeugt.
- `Storage.list_protocols()` liefert eine Übersicht der letzten Importe und wird in der UI angezeigt.
- Für Produktivbetrieb lassen sich beliebige SQLAlchemy-kompatible Datenbanken verwenden.

## Tests & Qualitätssicherung

Die Test-Suite stellt sicher, dass Parser, Pipeline, Konfiguration und Datenbank-Layer funktionieren. Nach Aktivieren der virtuellen Umgebung:

```bash
pip install -e .[dev]
pytest
```

## Fehlerbehebung

| Problem | Lösung |
| --- | --- |
| `ModuleNotFoundError` nach Start | Prüfen, ob `.venv` aktiviert ist (`source .venv/bin/activate`). |
| HTTP-Status 401/403 bei DIP | Gültigen API-Schlüssel in der Konfiguration oder per `MINE_DIP_API_KEY` hinterlegen. |
| Keine Summaries trotz Schlüssel | Prüfen, ob `mine import` ohne `--without-summaries` läuft und `gemini.api_key` gesetzt ist. |
| UI nicht erreichbar | Port prüfen oder mit `mine ui --ui-host 0.0.0.0 --ui-port 8080` starten. |

Weiterführende Details zur Architektur findest du in [`docs/architecture.md`](docs/architecture.md).
