# Architekturüberblick

Dieses Dokument beschreibt die wichtigsten Bausteine der modernisierten Repository-Struktur.

## Paketaufbau

```
src/bundestag_mine_refactor/
├── clients/              # Zugriff auf externe APIs (z. B. DIP)
├── config/               # Konfigurationsdaten und -ladefunktionen
├── core/                 # Domänenobjekte (Protokolle, Reden, …)
├── database/             # SQLAlchemy-Modelle und Storage-Fassade
├── parsing/              # Text-Pipeline zum Zerlegen von Protokollen
├── pipeline/             # Orchestrierung des ETL-Prozesses
└── summarization/        # Anbindung an Generative-AI-Dienste
```

## Datenfluss

1. **clients.DIPClient** ruft Metadaten und Volltexte der Plenarprotokolle ab.
2. **parsing.parse_speeches** zerteilt die Texte in einzelne Redebeiträge.
3. **database.Storage** persistiert Protokolle und Reden in einer relationalen Datenbank.
4. **summarization.GeminiSummarizer** erstellt optionale Zusammenfassungen.
5. **pipeline.ImportPipeline** verbindet alle Schritte und übernimmt das Fehler-Handling sowie die Reihenfolge.

## Konfiguration

Die zentrale Einstiegsfunktion `config.load_config` führt Standardwerte, optionale Konfigurationsdateien und Umgebungsvariablen (Prefix `BMR_`) zusammen. Dadurch lässt sich das Verhalten in Deployments und lokalen Entwicklungsumgebungen gleichermaßen steuern.

## CLI

Das Modul `cli` stellt den Kommandozeilen-Einstiegspunkt bereit. Es kapselt Parser-Aufbau, Pipeline-Initialisierung sowie Logging-Konfiguration.
