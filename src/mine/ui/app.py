"""NiceGUI powered control center for the Mine pipeline."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, Lock
from pathlib import Path
from typing import Deque, Dict, List, Optional

from nicegui import ui

from ..config import (
    AppConfig,
    DIPConfig,
    GeminiConfig,
    StorageConfig,
    load_config,
    resolve_config_path,
    save_config,
)
from ..database import ProtocolOverview, Storage, create_storage
from ..pipeline import PipelineEvent
from ..runtime import create_pipeline

_EVENT_LABELS: Dict[str, str] = {
    "start": "Start",
    "metadata": "Metadaten",
    "fetched": "Download",
    "parsed": "Analyse",
    "stored": "Gespeichert",
    "summaries": "Zusammenfassungen",
    "progress": "Fortschritt",
    "finished": "Abgeschlossen",
    "cancelled": "Abgebrochen",
    "error": "Fehler",
}


@dataclass(slots=True)
class LogEntry:
    timestamp: datetime
    stage: str
    message: str
    identifier: str | None = None
    title: str | None = None

    def to_row(self) -> Dict[str, str]:
        return {
            "time": self.timestamp.strftime("%H:%M:%S"),
            "stage": self.stage,
            "message": self.message,
            "identifier": self.identifier or "",
            "title": self.title or "",
        }


@dataclass
class RunState:
    is_running: bool = False
    processed: int = 0
    speech_total: int = 0
    summary_total: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_identifier: Optional[str] = None
    last_title: Optional[str] = None
    last_event: str = "idle"
    cancelled: bool = False
    error: Optional[str] = None
    log: Deque[LogEntry] = field(default_factory=lambda: deque(maxlen=200))
    revision: int = 0


class PipelineRunner:
    """Background helper coordinating pipeline execution and UI state."""

    def __init__(self, *, config: AppConfig, storage: Storage) -> None:
        self._config = config
        self._storage = storage
        self._lock = Lock()
        self._state = RunState()
        self._cancel_event: Event = Event()
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self, *, updated_since: Optional[str], limit: Optional[int], with_summaries: bool) -> bool:
        with self._lock:
            if self._state.is_running:
                return False
            self._state.is_running = True
            self._state.cancelled = False
            self._state.error = None
            self._state.processed = 0
            self._state.speech_total = 0
            self._state.summary_total = 0
            self._state.started_at = datetime.utcnow()
            self._state.finished_at = None
            self._state.last_identifier = None
            self._state.last_title = None
            self._state.last_event = "start"
            self._state.log.clear()
            self._state.revision += 1
        self._cancel_event.clear()

        async def _launch() -> None:
            def _run() -> int:
                resources = create_pipeline(
                    self._config,
                    skip_summaries=not with_summaries,
                    storage=self._storage,
                )
                try:
                    return resources.pipeline.run(
                        updated_since=updated_since,
                        limit=limit,
                        progress_callback=self._handle_event,
                        cancel_event=self._cancel_event,
                    )
                finally:
                    resources.close()

            try:
                await asyncio.to_thread(_run)
            finally:
                with self._lock:
                    self._task = None

        self._task = asyncio.create_task(_launch())
        return True

    def cancel(self) -> bool:
        with self._lock:
            if not self._state.is_running:
                return False
            self._cancel_event.set()
            return True

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            state = self._state
            status = self._resolve_status(state)
            return {
                "revision": state.revision,
                "status": status,
                "is_running": state.is_running,
                "processed": state.processed,
                "speech_total": state.speech_total,
                "summary_total": state.summary_total,
                "started_at": state.started_at,
                "finished_at": state.finished_at,
                "last_identifier": state.last_identifier,
                "last_title": state.last_title,
                "error": state.error,
                "log": [entry.to_row() for entry in list(state.log)],
            }

    def protocol_rows(self, limit: int = 25) -> List[Dict[str, str]]:
        protocols = self._storage.list_protocols(limit=limit)
        return [_protocol_to_row(p) for p in protocols]

    def is_running(self) -> bool:
        with self._lock:
            return self._state.is_running

    def update_resources(self, *, config: AppConfig, storage: Storage) -> None:
        with self._lock:
            if self._state.is_running:
                raise RuntimeError("Import läuft noch")
            self._config = config
            self._storage = storage
            self._state.revision += 1

    def current_config(self) -> AppConfig:
        with self._lock:
            return self._config

    def _handle_event(self, event: PipelineEvent) -> None:
        timestamp = datetime.utcnow()
        label = _EVENT_LABELS.get(event.kind, event.kind.title())
        identifier = event.metadata.identifier if event.metadata else None
        title = event.metadata.title if event.metadata else None
        with self._lock:
            state = self._state
            if event.kind == "start":
                state.is_running = True
                state.cancelled = False
                state.error = None
                state.processed = 0
                state.speech_total = 0
                state.summary_total = 0
                state.started_at = timestamp
                state.finished_at = None
                state.last_identifier = None
                state.last_title = None
                state.log.clear()
            elif event.kind == "stored" and event.speech_count:
                state.speech_total += event.speech_count
            elif event.kind == "summaries" and event.summary_count:
                state.summary_total += event.summary_count
            elif event.kind == "progress":
                state.processed = event.processed
                state.last_identifier = identifier
                state.last_title = title
            elif event.kind == "finished":
                state.is_running = False
                state.finished_at = timestamp
            elif event.kind == "cancelled":
                state.is_running = False
                state.cancelled = True
                state.finished_at = timestamp
            elif event.kind == "error":
                state.is_running = False
                state.error = event.message or "Unbekannter Fehler"
                state.finished_at = timestamp
            state.last_event = event.kind
            message = event.message or label
            state.log.append(
                LogEntry(
                    timestamp=timestamp,
                    stage=label,
                    message=message,
                    identifier=identifier,
                    title=title,
                )
            )
            state.revision += 1

    @staticmethod
    def _resolve_status(state: RunState) -> str:
        if state.is_running:
            return "running"
        if state.error:
            return "error"
        if state.cancelled:
            return "cancelled"
        if state.last_event == "finished":
            return "finished"
        return "idle"


def _protocol_to_row(protocol: ProtocolOverview) -> Dict[str, str]:
    date_str = protocol.date.isoformat() if protocol.date else "-"
    updated = protocol.updated_at.strftime("%Y-%m-%d %H:%M") if protocol.updated_at else "-"
    session = "-"
    if protocol.legislative_period or protocol.session_number:
        session = f"WP {protocol.legislative_period or '–'} / Sitzung {protocol.session_number or '–'}"
    return {
        "identifier": protocol.identifier,
        "date": date_str,
        "session": session,
        "title": protocol.title or "",
        "speeches": str(protocol.speech_count),
        "updated": updated,
    }


def _format_duration(started: Optional[datetime], finished: Optional[datetime], running: bool) -> str:
    if not started:
        return "-"
    end = datetime.utcnow() if running or not finished else finished
    delta = end - started
    total_seconds = int(delta.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d} h"
    return f"{minutes:02d}:{seconds:02d} min"


async def _update_protocol_table(runner: PipelineRunner, table) -> None:
    rows = await asyncio.to_thread(runner.protocol_rows)
    table.rows = rows


def run_ui(
    config: AppConfig,
    *,
    storage: Storage,
    host: str = "127.0.0.1",
    port: int = 8080,
    config_path: Path | None = None,
) -> None:
    """Start the NiceGUI based control center."""

    config_file_path = resolve_config_path(config_path)
    current_config = config
    current_storage = storage
    runner = PipelineRunner(config=current_config, storage=current_storage)

    def _config_summary_text(conf: AppConfig) -> str:
        return (
            f"**DIP API:** `{conf.dip.base_url}`\n"
            f"**Datenbank:** `{conf.storage.database_url}`\n"
            f"**Gemini aktiv:** {'Ja' if conf.gemini.api_key else 'Nein'}"
        )

    def _optional(text: Optional[str]) -> Optional[str]:
        value = (text or "").strip()
        return value or None

    def _require_text(value: Optional[str], label: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError(f"{label} darf nicht leer sein")
        return text

    def _parse_int(value: Optional[str], label: str) -> int:
        text = (value or "").strip()
        if not text:
            raise ValueError(f"{label} darf nicht leer sein")
        try:
            return int(float(text))
        except ValueError as exc:
            raise ValueError(f"{label} muss eine Ganzzahl sein") from exc

    def _parse_float(value: Optional[str], label: str) -> float:
        text = (value or "").strip()
        if not text:
            raise ValueError(f"{label} darf nicht leer sein")
        normalized = text.replace(",", ".")
        try:
            return float(normalized)
        except ValueError as exc:
            raise ValueError(f"{label} muss eine Zahl sein") from exc

    ui.colors(
        primary="#2563eb",
        secondary="#111827",
        accent="#f97316",
        positive="#22c55e",
        negative="#ef4444",
        info="#0ea5e9",
        warning="#facc15",
    )

    with ui.header().classes("items-center justify-between bg-primary text-white px-6 py-3 shadow-lg"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("gavel").classes("text-2xl")
            ui.label("Mine Control Center").classes("text-lg font-semibold")
        ui.badge("Kubuntu 24.04 ready", color="accent").classes("text-sm")

    with ui.row().classes("w-full max-w-6xl mx-auto mt-4 gap-6 flex-col lg:flex-row"):
        with ui.column().classes("w-full lg:w-1/3 gap-4"):
            with ui.card().classes("w-full shadow-md"):
                ui.label("Pipeline steuern").classes("text-base font-semibold mb-2")
                since_input = ui.input(
                    "Aktualisiert seit",
                    placeholder="2024-01-01T00:00:00",
                ).props("clearable")
                since_input.tooltip("Optionaler ISO-8601 Zeitstempel zur Filterung der Protokolle")
                limit_input = ui.number("Limit", value=None).props("type=number step=1 min=0")
                limit_input.tooltip("Maximale Anzahl von Protokollen pro Lauf (leer = unbegrenzt)")
                summary_switch = ui.switch(
                    "Gemini-Zusammenfassungen aktivieren",
                    value=bool(current_config.gemini.api_key),
                )
                summary_switch.tooltip(
                    "Erzeugt automatisch Kurzfassungen, sofern ein gültiger API-Key konfiguriert ist"
                )
                with ui.row().classes("gap-2 mt-3"):
                    start_button = ui.button("Import starten", color="primary")
                    stop_button = ui.button("Stopp", color="negative")
                    stop_button.disable()
            with ui.card().classes("w-full shadow-md gap-2"):
                ui.label("Konfiguration").classes("text-base font-semibold")
                config_path_label = ui.label(f"Datei: {config_file_path}").classes("text-xs text-gray-500")
                config_summary = ui.markdown(_config_summary_text(current_config)).classes("text-sm")
                with ui.tabs().classes("w-full mt-1") as config_tabs:
                    dip_tab = ui.tab("DIP API")
                    gemini_tab = ui.tab("Gemini")
                    storage_tab = ui.tab("Datenbank")
                with ui.tab_panels(config_tabs, value=dip_tab).classes("w-full"):
                    with ui.tab_panel(dip_tab):
                        ui.label("Zugangsdaten für das Dokumentations- und Informationssystem.").classes(
                            "text-xs text-gray-500 mb-2"
                        )
                        dip_base_input = ui.input("Basis-URL", value=current_config.dip.base_url)
                        dip_base_input.classes("w-full")
                        dip_api_key_input = ui.input("API-Schlüssel", value=current_config.dip.api_key or "")
                        dip_api_key_input.props("type=password clearable")
                        dip_api_key_input.classes("w-full")
                        dip_timeout_input = ui.input(
                            "Timeout (Sekunden)",
                            value=f"{current_config.dip.timeout:g}",
                        ).props("type=number step=0.1 min=0")
                        dip_timeout_input.classes("w-full")
                        dip_max_retries_input = ui.input(
                            "Maximale Wiederholungen",
                            value=str(current_config.dip.max_retries),
                        ).props("type=number step=1 min=0")
                        dip_max_retries_input.classes("w-full")
                        dip_page_size_input = ui.input(
                            "Seitengröße",
                            value=str(current_config.dip.page_size),
                        ).props("type=number step=1 min=1")
                        dip_page_size_input.classes("w-full")
                    with ui.tab_panel(gemini_tab):
                        ui.label("Optionale Konfiguration für automatische Zusammenfassungen.").classes(
                            "text-xs text-gray-500 mb-2"
                        )
                        gemini_api_key_input = ui.input("API-Schlüssel", value=current_config.gemini.api_key or "")
                        gemini_api_key_input.props("type=password clearable")
                        gemini_api_key_input.classes("w-full")
                        gemini_model_input = ui.input("Modell", value=current_config.gemini.model)
                        gemini_model_input.classes("w-full")
                        gemini_base_url_input = ui.input("Basis-URL", value=current_config.gemini.base_url)
                        gemini_base_url_input.classes("w-full")
                        gemini_timeout_input = ui.input(
                            "Timeout (Sekunden)",
                            value=f"{current_config.gemini.timeout:g}",
                        ).props("type=number step=0.1 min=0")
                        gemini_timeout_input.classes("w-full")
                        gemini_max_retries_input = ui.input(
                            "Maximale Wiederholungen",
                            value=str(current_config.gemini.max_retries),
                        ).props("type=number step=1 min=0")
                        gemini_max_retries_input.classes("w-full")
                        gemini_safety_switch = ui.switch(
                            "Safety-Einstellungen aktivieren",
                            value=current_config.gemini.enable_safety_settings,
                        )
                    with ui.tab_panel(storage_tab):
                        ui.label("Datenbank-Ziel für Protokolle und Redebeiträge.").classes(
                            "text-xs text-gray-500 mb-2"
                        )
                        storage_url_input = ui.input(
                            "SQLAlchemy URL",
                            value=current_config.storage.database_url,
                        )
                        storage_url_input.classes("w-full")
                        storage_echo_switch = ui.switch(
                            "SQL-Debug-Ausgaben aktivieren",
                            value=current_config.storage.echo_sql,
                        )
                with ui.row().classes("gap-2 mt-3"):
                    save_button = ui.button("Speichern", color="primary", icon="save")
                    reload_button = ui.button("Neu laden", icon="refresh")
        with ui.column().classes("w-full lg:w-2/3 gap-4"):
            with ui.card().classes("w-full shadow-md"):
                ui.label("Laufzeit-Monitor").classes("text-base font-semibold mb-2")
                with ui.row().classes("gap-6 flex-wrap"):
                    status_badge = ui.badge("Bereit", color="positive").classes("text-sm")
                    processed_value = ui.label("0").classes("text-3xl font-semibold")
                    processed_caption = ui.label("Verarbeitete Protokolle").classes("text-xs text-gray-500")
                    speech_value = ui.label("0").classes("text-3xl font-semibold")
                    speech_caption = ui.label("Gespeicherte Reden").classes("text-xs text-gray-500")
                    summary_value = ui.label("0").classes("text-3xl font-semibold")
                    summary_caption = ui.label("Aktualisierte Zusammenfassungen").classes("text-xs text-gray-500")
                last_protocol_label = ui.label("Noch kein Import durchgeführt").classes("text-sm mt-2 text-gray-600")
                duration_label = ui.label("-").classes("text-sm text-gray-500")
                error_alert = ui.label("").classes("text-sm text-negative")
                error_alert.visible = False
            with ui.card().classes("w-full shadow-md"):
                ui.label("Live-Log").classes("text-base font-semibold mb-2")
                log_columns = [
                    {"name": "time", "label": "Zeit", "field": "time", "align": "left"},
                    {"name": "stage", "label": "Phase", "field": "stage", "align": "left"},
                    {"name": "identifier", "label": "ID", "field": "identifier", "align": "left"},
                    {"name": "title", "label": "Titel", "field": "title", "align": "left"},
                    {"name": "message", "label": "Details", "field": "message", "align": "left"},
                ]
                log_table = ui.table(columns=log_columns, rows=[], row_key="time").classes("w-full")
                log_table.props("dense wrap-cells flat")
    with ui.card().classes("w-full max-w-6xl mx-auto mt-4 shadow-md"):
        with ui.row().classes("items-center justify-between"):
            ui.label("Persistierte Protokolle").classes("text-base font-semibold")
            refresh_button = ui.button("Aktualisieren", icon="refresh")
        protocol_columns = [
            {"name": "identifier", "label": "ID", "field": "identifier", "align": "left"},
            {"name": "date", "label": "Datum", "field": "date", "align": "left"},
            {"name": "session", "label": "Wahlperiode / Sitzung", "field": "session", "align": "left"},
            {"name": "title", "label": "Titel", "field": "title", "align": "left"},
            {"name": "speeches", "label": "Reden", "field": "speeches", "align": "right"},
            {"name": "updated", "label": "Zuletzt aktualisiert", "field": "updated", "align": "left"},
        ]
        protocol_table = ui.table(columns=protocol_columns, rows=[], row_key="identifier").classes("w-full")
        protocol_table.props("wrap-cells flat")

    def populate_fields(conf: AppConfig) -> None:
        dip_base_input.set_value(conf.dip.base_url)
        dip_api_key_input.set_value(conf.dip.api_key or "")
        dip_timeout_input.set_value(f"{conf.dip.timeout:g}")
        dip_max_retries_input.set_value(str(conf.dip.max_retries))
        dip_page_size_input.set_value(str(conf.dip.page_size))
        gemini_api_key_input.set_value(conf.gemini.api_key or "")
        gemini_model_input.set_value(conf.gemini.model)
        gemini_base_url_input.set_value(conf.gemini.base_url)
        gemini_timeout_input.set_value(f"{conf.gemini.timeout:g}")
        gemini_max_retries_input.set_value(str(conf.gemini.max_retries))
        gemini_safety_switch.set_value(conf.gemini.enable_safety_settings)
        storage_url_input.set_value(conf.storage.database_url)
        storage_echo_switch.set_value(conf.storage.echo_sql)

    def update_summary(conf: AppConfig) -> None:
        config_summary.set_content(_config_summary_text(conf))
        config_path_label.set_text(f"Datei: {config_file_path}")

    async def handle_start() -> None:
        since_value = (since_input.value or "").strip()
        since = since_value or None
        limit_raw = limit_input.value
        limit: Optional[int]
        if limit_raw in (None, ""):
            limit = None
        else:
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                ui.notify("Bitte eine gültige Ganzzahl für das Limit eingeben", color="negative")
                return
            if limit < 0:
                ui.notify("Das Limit darf nicht negativ sein", color="negative")
                return
        started = await runner.start(
            updated_since=since,
            limit=limit,
            with_summaries=summary_switch.value,
        )
        if not started:
            ui.notify("Es läuft bereits ein Import.", color="warning")
        else:
            ui.notify("Import gestartet", color="positive")

    async def handle_stop() -> None:
        if runner.cancel():
            ui.notify("Import wird gestoppt…", color="warning")
        else:
            ui.notify("Kein Import aktiv", color="info")

    async def refresh_protocols() -> None:
        refresh_button.disable()
        try:
            await _update_protocol_table(runner, protocol_table)
        finally:
            refresh_button.enable()

    async def handle_save_config() -> None:
        nonlocal current_config, current_storage, config_file_path
        if runner.is_running():
            ui.notify("Bitte beenden Sie den laufenden Import, bevor die Konfiguration gespeichert wird.", color="warning")
            return

        try:
            new_config = AppConfig(
                dip=DIPConfig(
                    base_url=_require_text(dip_base_input.value, "DIP Basis-URL"),
                    api_key=_optional(dip_api_key_input.value),
                    timeout=_parse_float(dip_timeout_input.value, "DIP Timeout"),
                    max_retries=_parse_int(dip_max_retries_input.value, "DIP Wiederholungen"),
                    page_size=_parse_int(dip_page_size_input.value, "DIP Seitengröße"),
                ),
                gemini=GeminiConfig(
                    api_key=_optional(gemini_api_key_input.value),
                    base_url=_require_text(gemini_base_url_input.value, "Gemini Basis-URL"),
                    model=_require_text(gemini_model_input.value, "Gemini Modell"),
                    timeout=_parse_float(gemini_timeout_input.value, "Gemini Timeout"),
                    max_retries=_parse_int(gemini_max_retries_input.value, "Gemini Wiederholungen"),
                    enable_safety_settings=bool(gemini_safety_switch.value),
                ),
                storage=StorageConfig(
                    database_url=_require_text(storage_url_input.value, "Datenbank-URL"),
                    echo_sql=bool(storage_echo_switch.value),
                ),
            )
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            return

        storage_changed = (
            new_config.storage.database_url != current_config.storage.database_url
            or new_config.storage.echo_sql != current_config.storage.echo_sql
        )

        new_storage = current_storage
        old_storage: Optional[Storage] = None
        if storage_changed:
            try:
                new_storage = await asyncio.to_thread(
                    create_storage,
                    new_config.storage.database_url,
                    echo=new_config.storage.echo_sql,
                )
            except Exception as exc:  # pragma: no cover - depends on runtime environment
                ui.notify(f"Datenbankverbindung fehlgeschlagen: {exc}", color="negative")
                return
            old_storage = current_storage

        try:
            saved_path = await asyncio.to_thread(save_config, new_config, config_file_path)
        except Exception as exc:  # pragma: no cover - defensive I/O handling
            if storage_changed and new_storage is not current_storage:
                new_storage.dispose()
            ui.notify(f"Konfiguration konnte nicht gespeichert werden: {exc}", color="negative")
            return

        try:
            runner.update_resources(config=new_config, storage=new_storage)
        except RuntimeError as exc:  # pragma: no cover - defensive
            if storage_changed and new_storage is not current_storage:
                new_storage.dispose()
            ui.notify(str(exc), color="negative")
            return

        if old_storage is not None:
            old_storage.dispose()

        current_config = new_config
        current_storage = new_storage
        config_file_path = saved_path
        populate_fields(new_config)
        update_summary(new_config)
        summary_switch.set_value(bool(new_config.gemini.api_key))
        ui.notify(f"Konfiguration gespeichert ({saved_path})", color="positive")
        if storage_changed:
            asyncio.create_task(refresh_protocols())

    async def handle_reload_config() -> None:
        nonlocal current_config, current_storage
        if runner.is_running():
            ui.notify("Bitte beenden Sie den laufenden Import, bevor die Konfiguration neu geladen wird.", color="warning")
            return
        try:
            reloaded_config = await asyncio.to_thread(load_config, config_file_path)
        except Exception as exc:  # pragma: no cover - defensive I/O handling
            ui.notify(f"Konfiguration konnte nicht geladen werden: {exc}", color="negative")
            return

        storage_changed = (
            reloaded_config.storage.database_url != current_config.storage.database_url
            or reloaded_config.storage.echo_sql != current_config.storage.echo_sql
        )

        new_storage = current_storage
        old_storage: Optional[Storage] = None
        if storage_changed:
            try:
                new_storage = await asyncio.to_thread(
                    create_storage,
                    reloaded_config.storage.database_url,
                    echo=reloaded_config.storage.echo_sql,
                )
            except Exception as exc:  # pragma: no cover
                ui.notify(f"Datenbankverbindung fehlgeschlagen: {exc}", color="negative")
                return
            old_storage = current_storage

        try:
            runner.update_resources(config=reloaded_config, storage=new_storage)
        except RuntimeError as exc:  # pragma: no cover
            if storage_changed and new_storage is not current_storage:
                new_storage.dispose()
            ui.notify(str(exc), color="negative")
            return

        if old_storage is not None:
            old_storage.dispose()

        current_config = reloaded_config
        current_storage = new_storage
        populate_fields(reloaded_config)
        update_summary(reloaded_config)
        summary_switch.set_value(bool(reloaded_config.gemini.api_key))
        ui.notify("Konfiguration neu geladen", color="info")
        if storage_changed:
            asyncio.create_task(refresh_protocols())

    populate_fields(current_config)
    update_summary(current_config)

    start_button.on("click", handle_start)
    stop_button.on("click", handle_stop)
    refresh_button.on("click", refresh_protocols)
    save_button.on("click", handle_save_config)
    reload_button.on("click", handle_reload_config)

    last_revision = -1
    last_status = ""
    status_colors = {
        "idle": "info",
        "running": "accent",
        "finished": "positive",
        "cancelled": "warning",
        "error": "negative",
    }

    def update_components() -> None:
        nonlocal last_revision, last_status
        snapshot = runner.snapshot()
        if snapshot["revision"] == last_revision:
            return
        last_revision = snapshot["revision"]
        status = snapshot["status"]
        status_badge.set_text({
            "idle": "Bereit",
            "running": "Laufend",
            "finished": "Fertig",
            "cancelled": "Abgebrochen",
            "error": "Fehler",
        }.get(status, status.title()))
        status_badge.props(f"color={status_colors.get(status, 'info')}")
        start_button.disable() if snapshot["is_running"] else start_button.enable()
        stop_button.enable() if snapshot["is_running"] else stop_button.disable()
        processed_value.set_text(str(snapshot["processed"]))
        speech_value.set_text(str(snapshot["speech_total"]))
        summary_value.set_text(str(snapshot["summary_total"]))
        last_identifier = snapshot.get("last_identifier")
        if last_identifier:
            title = snapshot.get("last_title") or ""
            last_protocol_label.set_text(f"Zuletzt verarbeitet: {last_identifier} – {title}")
        else:
            last_protocol_label.set_text("Noch kein Import durchgeführt")
        duration_label.set_text(
            _format_duration(
                snapshot.get("started_at"),
                snapshot.get("finished_at"),
                snapshot.get("is_running"),
            )
        )
        error_message = snapshot.get("error")
        if error_message:
            error_alert.set_text(error_message)
            error_alert.visible = True
        else:
            error_alert.visible = False
        log_table.rows = snapshot["log"]
        if status != last_status and status in {"finished", "cancelled", "error"}:
            asyncio.create_task(refresh_protocols())
        last_status = status

    ui.timer(0.5, update_components)
    ui.on_startup(lambda: asyncio.create_task(refresh_protocols()))
    ui.run(reload=False, host=host, port=port, title="Mine Control Center")
