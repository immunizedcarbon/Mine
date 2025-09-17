# Mine

Eine modernisierte Python-Pipeline zum Abrufen, Analysieren und Archivieren von Plenarprotokollen des Deutschen Bundestags. Die Anwendung kombiniert einen zuverlässigen ETL-Prozess, eine NiceGUI-basierte Oberfläche sowie optionale Textzusammenfassungen über Googles Gemini-API.

## Inhalt

- [Funktionsumfang](#funktionsumfang)
- [Projektstruktur](#projektstruktur)
- [Systemvoraussetzungen](#systemvoraussetzungen)
- [Installation auf Kubuntu 24.04](#installation-auf-kubuntu-2404)
- [Konfiguration](#konfiguration)
- [Nutzung](#nutzung)
  - [Kommandozeile](#kommandozeile)
  - [Grafische Oberfläche](#grafische-oberfläche)
  - [Programmierbare Nutzung](#programmierbare-nutzung)
- [Datenbank & Persistenz](#datenbank--persistenz)
- [Tests & Qualitätssicherung](#tests--qualitätssicherung)
- [Fehlerbehebung](#fehlerbehebung)
- [Weiterführende Informationen](#weiterführende-informationen)

## Funktionsumfang

- **Protokolle abrufen:** Der `DIPClient` kommuniziert mit der offiziellen DIP-API und lädt Metadaten sowie Volltexte der Plenarprotokolle.
- **Texte zerlegen:** `parse_speeches` identifiziert Sprecher*innen, Parteien, Rollen und entfernt Regieanweisungen, um saubere Redebeiträge zu erzeugen.
- **Daten speichern:** Der `Storage`-Layer legt Protokolle und Reden in einer relationalen Datenbank ab, standardmäßig SQLite.
- **Zusammenfassungen erzeugen (optional):** Mit einem Gemini-API-Schlüssel erstellt der `GeminiSummarizer` Kurzfassungen für Reden und speichert sie im Datenbestand.
- **Pipeline orchestrieren:** `ImportPipeline` koordiniert Abruf, Parsing, Persistenz und optionale Summaries, inklusive Abbruchmöglichkeit und Fortschrittsmeldungen.
- **Bedienoberfläche:** Die NiceGUI-App visualisiert Status, Log und gespeicherte Protokolle und ermöglicht das Starten/Stoppen von Importläufen.

## Projektstruktur

```
.
├── docs/
│   └── architecture.md      # Technischer Architekturüberblick
├── pyproject.toml           # Paket-Metadaten & optionale Dev-Abhängigkeiten
├── requirements.txt         # Minimale Laufzeitabhängigkeiten
├── src/
│   └── mine/
│       ├── __main__.py      # Einstiegspunkt für `python -m`
│       ├── cli.py           # Kommandozeileninterface
│       ├── clients/         # HTTP-Clients (DIP)
│       ├── config/          # Konfiguration & Settings
│       ├── core/            # Domänenobjekte
│       ├── database/        # SQLAlchemy-Modelle & Storage-Fassade
│       ├── parsing/         # Text-Parser für Redebeiträge
│       ├── pipeline/        # ETL-Orchestrierung
│       ├── summarization/   # Gemini-Anbindung
│       └── ui/              # NiceGUI-Control-Center
└── tests/                   # Pytest-Suite
```

## Systemvoraussetzungen

- Kubuntu 24.04 (oder ein kompatibles Ubuntu-24.04-Derivat)
- Python ≥ 3.10 (empfohlen: das vorinstallierte Python 3.12)
- Git und gängige Build-Werkzeuge (`build-essential`)
- Optional: Zugangsdaten für die [DIP-API](https://dip.bundestag.de) und einen [Google Gemini API Key](https://ai.google.dev)

## Installation auf Kubuntu 24.04

Die folgenden Schritte lassen sich direkt im Terminal ausführen. Jeder Schritt baut auf dem vorherigen auf.

1. **System vorbereiten** – Paketquellen aktualisieren und benötigte Tools installieren:

   ```bash
   sudo apt update
   sudo apt install -y python3.12 python3.12-venv python3-pip git build-essential
   ```

   Tipp: Mit `python3 --version` lässt sich prüfen, ob Python 3.12 aktiv ist.

2. **Repository klonen** – Quellcode herunterladen und ins Projektverzeichnis wechseln:

   ```bash
   git clone https://github.com/immunizedcarbon/Mine.git
   cd Mine
   ```

3. **Virtuelle Umgebung einrichten** – schützt das System vor Versionskonflikten:

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

   Im Terminal sollte nun ein Präfix wie `(.venv)` erscheinen. Zum Deaktivieren später `deactivate` eingeben.

4. **Pip aktualisieren und Projekt installieren**:

   ```bash
   python -m pip install --upgrade pip
   pip install -e .
   ```

   Alternativ kann die minimalistische Variante verwendet werden:

   ```bash
   pip install -r requirements.txt
   ```

5. **(Optional) Entwicklungswerkzeuge installieren** – inklusive Test-Suite:

   ```bash
   pip install -e .[dev]
   ```

Nach Updates des Quellcodes genügt innerhalb der aktivierten virtuellen Umgebung `pip install -e .`, um die Abhängigkeiten zu aktualisieren.

## Konfiguration

`load_config` kombiniert Standardwerte, optionale JSON-Dateien und Umgebungsvariablen mit dem Präfix `MINE_`. Ohne eigene Einstellungen wird eine lokale SQLite-Datenbank (`mine.db`) verwendet.

### Konfigurationsdatei anlegen

Die Anwendung sucht automatisch nach folgenden Dateien (in dieser Reihenfolge):

1. `./mine.json`
2. `~/.config/mine/config.json`

Beispielinhalt:

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
    "database_url": "sqlite:///mine.db"
  }
}
```

### Umgebungsvariablen

| Variable                        | Bedeutung                                                        |
|---------------------------------|------------------------------------------------------------------|
| `MINE_DIP_API_KEY`               | API-Key für das DIP-Portal                                       |
| `MINE_DIP_BASE_URL`              | Alternative Basis-URL des DIP-Endpunkts                          |
| `MINE_DIP_TIMEOUT` / `MINE_DIP_MAX_RETRIES` | HTTP-Timeout (Sekunden) bzw. Retry-Anzahl                |
| `MINE_DIP_PAGE_SIZE`             | Seitengröße für die Protokollabfrage                             |
| `MINE_GEMINI_API_KEY`            | API-Key für Gemini-Zusammenfassungen                             |
| `MINE_GEMINI_ENABLE_SAFETY_SETTINGS` | `true` aktiviert die Gemini-Safety-Filter                     |
| `MINE_STORAGE_DATABASE_URL`      | Vollständige SQLAlchemy-URL (z. B. `postgresql+psycopg://…`)     |
| `MINE_STORAGE_ECHO_SQL`          | `true`/`false` für SQL-Debug-Ausgaben                            |

Umgebungsvariablen überschreiben Werte aus der Datei. Mit `--config /pfad/zur/datei.json` lässt sich beim CLI-Aufruf eine spezifische Datei laden.

## Nutzung

### Kommandozeile

Die Installation stellt das Skript `mine` bereit. Zwei Befehle stehen zur Verfügung:

- `mine import` startet den ETL-Lauf.
- `mine ui` startet die grafische Oberfläche.

Häufige Optionen:

| Option                 | Beschreibung                                                     |
|------------------------|------------------------------------------------------------------|
| `--config DATEI`       | Explizite Konfigurationsdatei laden                               |
| `--since ISO-ZEIT`     | Nur Protokolle importieren, die seitdem aktualisiert wurden       |
| `--limit N`            | Anzahl der Protokolle begrenzen                                   |
| `--without-summaries`  | Gemini-Zusammenfassungen trotz vorhandenem Schlüssel überspringen |
| `--ui-host HOST` / `--ui-port PORT` | Host & Port für den UI-Server (nur bei `ui`)           |

Beispiel: `mine import --since 2024-01-01T00:00:00 --limit 10`

Während des Laufs meldet die Pipeline jeden Fortschritt über `PipelineEvent`-Objekte; Fehler führen zu einem Abbruch mit aussagekräftigem Logeintrag.

### Grafische Oberfläche

Der UI-Befehl startet eine NiceGUI-App (Standard: `http://127.0.0.1:8080`). Die Oberfläche bietet:

- Start/Stopp-Schalter für Importläufe
- Live-Monitoring von Fortschritt, Reden und erzeugten Zusammenfassungen
- Log-Tabelle mit Zeitstempeln und Verarbeitungsphasen
- Snapshot-Tabelle aller gespeicherten Protokolle inklusive Sitzung, Datum und Redeanzahl
- Einblendung von Fehlern und Laufzeitdauer je Import

Die UI greift auf dieselbe Konfiguration wie das CLI zu und verwendet den gemeinsamen `Storage`-Layer. Mit `--ui-host 0.0.0.0` lässt sich die Oberfläche im Netzwerk freigeben.

### Programmierbare Nutzung

Alle Kernkomponenten können direkt aus Python-Skripten genutzt werden:

```python
from mine import ImportPipeline, clients, config, database

app_config = config.load_config()
dip_client = clients.DIPClient(app_config.dip.base_url, app_config.dip.api_key)
storage = database.create_storage(app_config.storage.database_url)
pipeline = ImportPipeline(dip_client=dip_client, storage=storage)
pipeline.run(limit=1)
```

Über `runtime.create_pipeline` lassen sich außerdem `GeminiSummarizer` und bestehende Ressourcen kombinieren.

## Datenbank & Persistenz

- Standardziel ist `sqlite:///mine.db` im Projektverzeichnis.
- Tabellen `protocols` und `speeches` werden automatisch angelegt und enthalten Metadaten, Redebeiträge, optionale Summaries und Zeitstempel.
- Über `Storage.list_protocols()` lässt sich ein Überblick der zuletzt verarbeiteten Protokolle abrufen; die UI nutzt diese Funktion für die Tabelle „Persistierte Protokolle“.
- Für produktive Deployments können beliebige SQLAlchemy-kompatible Datenbanken eingesetzt werden (z. B. PostgreSQL). Passen Sie hierzu `storage.database_url` an.

## Tests & Qualitätssicherung

Die Test-Suite basiert auf `pytest` und deckt Clients, Parser, Pipeline, Konfiguration und Datenbank-Übersichten ab.

```bash
source .venv/bin/activate   # falls noch nicht aktiv
pip install -e .[dev]
pytest
```

Weitere Empfehlungen:

- `python -m pip list --outdated` zur Pflege der Abhängigkeiten
- Versionskontrolle der Datenbank mithilfe externer Tools wie Alembic (nicht enthalten)

## Fehlerbehebung

| Problem                                         | Lösungsvorschlag |
|-------------------------------------------------|------------------|
| `ModuleNotFoundError` nach Installation         | Prüfen, ob die virtuelle Umgebung aktiv ist (`source .venv/bin/activate`). |
| `403 Forbidden` beim DIP-Abruf                  | API-Key hinterlegen oder die Anfrage ohne Schlüssel auf öffentlich zugängliche Dokumente beschränken. |
| Gemini-Zusammenfassungen werden übersprungen    | `MINE_GEMINI_API_KEY` setzen bzw. in der Konfigurationsdatei hinterlegen und nicht `--without-summaries` verwenden. |
| SQLite-Datei gesperrt                           | Andere Prozesse schließen oder auf eine separate Datenbank (z. B. PostgreSQL) ausweichen. |
| UI unter `http://127.0.0.1:8080` nicht erreichbar | Firewall/Port prüfen oder mit `--ui-host 0.0.0.0 --ui-port 8080` neu starten. |

## Weiterführende Informationen

- [Architekturüberblick](docs/architecture.md)
- Offizielle Schnittstellen:
  - [DIP Dokumentationsportal](https://dip.bundestag.de)
  - [Google AI Studio – Gemini](https://ai.google.dev)
