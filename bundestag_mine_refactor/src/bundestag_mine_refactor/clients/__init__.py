"""HTTP clients used by the Bundestags-Mine pipeline."""
from __future__ import annotations

from .dip import DIPClient, DIPClientError

__all__ = ["DIPClient", "DIPClientError"]
