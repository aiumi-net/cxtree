from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config


@dataclass
class FileEntry:
    path: Path
    rel: str  # relative path from the walk root, e.g. "src/utils.py"


def walk_dir(root: Path, config: Config, base: Path | None = None) -> list[FileEntry]:
    """Walk *root* recursively and return matching FileEntry list.

    Files are sorted: directories before files, then alphabetically.
    *base* is the path used for computing relative paths (defaults to *root*).
    """
    if base is None:
        base = root

    entries: list[FileEntry] = []
    try:
        items = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return entries

    for item in items:
        name = item.name

        if any(name.startswith(p) for p in config.exclude_startswith):
            continue

        if item.is_dir():
            if name in config.exclude_folders:
                continue
            entries.extend(walk_dir(item, config, base))
        elif item.is_file():
            ext = item.suffix.lstrip(".")
            # Extensionless files (e.g. Dockerfile) are matched by their full name
            key = ext if ext else item.name
            if config.include_extensions and key not in config.include_extensions:
                continue
            entries.append(FileEntry(path=item, rel=str(item.relative_to(base))))

    return entries
