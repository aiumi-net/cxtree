from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cxtree")
except PackageNotFoundError:
    __version__ = "unknown"
