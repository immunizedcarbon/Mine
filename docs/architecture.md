# Architekturüberblick

Dieses Dokument fasst die wichtigsten Bausteine, Abläufe und Datenstrukturen der modernisierten Bundestag-Mine-Pipeline zusammen.

## Komponentenlandschaft

Die Anwendung ist als installierbares Python-Paket aufgebaut. Jeder Unterordner in `src/bundestag_mine_refactor` erfüllt eine klar abgegrenzte Aufgabe:

| Modul                   | Verantwortung |
|-------------------------|---------------|
| `clients`               | HTTP-Clients (aktuell nur `DIPClient`) für das Laden von Metadaten und Volltexten über die DIP-API.
| `config`                | Dataclasses für Konfigurationswerte sowie `load_config`, das Defaults, JSON-Dateien und `BMR_*`-Umgebungsvariablen zusammenführt.
| `core`                  | Typisierte Domänenobjekte (`ProtocolMetadata`, `ProtocolDocument`, `Speech`).
| `database`              | SQLAlchemy-Modelle (`Protocol`, `SpeechModel`) und eine `Storage`-Fassade inklusive Schema-Erzeugung.
| `parsing`               | Funktionen zum Zerlegen von Protokolltexten in einzelne Reden und Metadaten-Erkennung.
| `pipeline`              | Die End-to-End-Orchestrierung (`ImportPipeline`) mit Fortschrittsereignissen und optionalem Abbruch.
| `summarization`         | `GeminiSummarizer` zur Interaktion mit Googles Generative-AI-API.
| `ui`                    | NiceGUI-basierte Kontrolloberfläche samt Laufzeitüberwachung.
| `runtime`               | Helfer zum Kombinieren der Komponenten zu lauffähigen Pipelines (`create_pipeline`).

Der Einstieg für `python -m bundestag_mine_refactor` delegiert an das CLI (`cli.main`), welches wiederum auf `runtime.create_pipeline` und `ui.run_ui` zurückgreift.

## Ablauf des Imports

1. **Konfiguration laden:** `cli.main` ruft `load_config` auf und erstellt daraus `AppConfig`.
2. **Pipeline zusammenbauen:** `runtime.create_pipeline` initialisiert `DIPClient`, `Storage` und optional `GeminiSummarizer` und kapselt sie in `PipelineResources`.
3. **Metadaten streamen:** `DIPClient.iter_protocols` verwendet Cursor-Pagination, um Protokolle seitenweise abzurufen.
4. **Volltext laden:** Für jedes Protokoll wird der komplette Text (`fetch_protocol_text`) nachgeladen.
5. **Reden parsen:** `parse_speeches` erkennt Sprecher*innen, Parteien, Rollen und bereinigt Bühnenanweisungen.
6. **Persistieren:** `Storage.upsert_protocol` legt/aktualisiert den Datenbankeintrag, `Storage.replace_speeches` ersetzt alle Reden eines Protokolls atomar.
7. **Summaries erzeugen (optional):** `Storage.pending_summaries` liefert Reden ohne Zusammenfassung; `GeminiSummarizer.summarize` erzeugt Kurzfassungen.
8. **Fortschritt signalisieren:** Nach jedem Schritt werden `PipelineEvent`-Objekte erzeugt (z. B. `start`, `parsed`, `stored`, `summaries`, `finished`). Cancel-Events beenden den Lauf frühzeitig.

Der gesamte Import läuft synchron, lässt sich jedoch über `asyncio.to_thread` aus der UI heraus im Hintergrund ausführen.

## Persistenzmodell

Die lokale SQLite-Datenbank (oder eine alternative SQLAlchemy-Zieldatenbank) besteht aus zwei Tabellen:

- `protocols`: speichert ID, Wahlperiode, Sitzungsnummer, Datum, Titel sowie `created_at`/`updated_at`-Zeitstempel.
- `speeches`: enthält zugehörige Reden mit Sequenznummer, Sprecher*in, Partei/Rolle, Volltext, optionaler Zusammenfassung, Sentiment/Topics-Platzhaltern und Zeitstempeln.

`Storage.ensure_schema` legt das Schema automatisch an. `Storage.list_protocols` erstellt eine aggregierte Übersicht inklusive Redeanzahl, die sowohl von Tests als auch der UI genutzt wird.

## Konfigurationsquellen

- **Defaultwerte:** in `config.settings` definiert (z. B. DIP-Basis-URL, SQLite-Datenbank).
- **JSON-Dateien:** `bundestag_mine_refactor.json` im Projekt oder `~/.config/bundestag_mine_refactor/config.json` für nutzerspezifische Einstellungen.
- **Umgebungsvariablen:** Präfix `BMR_` und Schema `BMR_SECTION_FIELD`. Werte werden typkonvertiert (z. B. `true` → `bool`).
- **CLI-Parameter:** `--config` erlaubt das Laden einer expliziten Konfigurationsdatei.

Die Quellen werden in der obigen Reihenfolge zusammengeführt; spätere Quellen überschreiben frühere.

## Benutzeroberfläche

Die NiceGUI-App (`ui.app`) erstellt eine `PipelineRunner`-Instanz, die Importe in einem Hintergrundthread startet und den UI-Status regelmäßig aktualisiert. Kernbestandteile:

- Steuerkarte mit Eingabefeldern für `--since`, `--limit` und einen Schalter für Gemini-Zusammenfassungen.
- Live-Monitor mit Status-Badge, Zählern (Protokolle, Reden, Summaries), zuletzt verarbeitetem Protokoll und Laufzeit.
- Log-Tabelle auf Basis von `PipelineEvent`-Meldungen (max. 200 Einträge, zirkulärer Puffer).
- Tabelle „Persistierte Protokolle“, gespeist von `Storage.list_protocols()` und per Button aktualisierbar.
- Periodischer `ui.timer`, der UI-Komponenten mit dem aktuellen Snapshot synchronisiert.

Die UI verwendet dieselbe `Storage`-Instanz wie die Pipeline, wodurch keine konkurrierenden Datenbankverbindungen entstehen.

## Tests

Die Pytest-Suite prüft zentrale Funktionen:

- Cursor-Nutzung und Feldmapping des `DIPClient`.
- Typkonvertierung und Fehlerbehandlung der Konfiguration.
- Parser-Logik für Reden inklusive Umgang mit Regieanweisungen.
- Pipeline-Lebenszyklus (Events, Persistenz, Abbruch).
- Datenbank-Übersichten (`list_protocols`).

Damit wird sichergestellt, dass die Dokumentation und der beschriebene Ablauf mit der Implementierung übereinstimmen.
