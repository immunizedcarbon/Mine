"""Interactive control center for the Bundestag Mine pipeline."""
from __future__ import annotations

from importlib import import_module
from typing import Any

try:
    run_ui = import_module("bundestag_mine_refactor.ui.app").run_ui  # type: ignore[attr-defined]
except ModuleNotFoundError as exc:  # pragma: no cover - triggered when nicegui is absent
    if exc.name != "nicegui":
        raise

    def run_ui(*_: Any, **__: Any) -> None:
        raise ModuleNotFoundError(
            "NiceGUI muss installiert sein, um die grafische Oberfläche zu starten. "
            "Installieren Sie das Extra mit `pip install bundestag-mine-refactor[nicegui]` "
            "oder direkt `pip install nicegui>=1.4.17`."
        ) from exc

__all__ = ["run_ui"]
