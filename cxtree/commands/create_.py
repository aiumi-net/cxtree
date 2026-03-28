from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

from ..models import (ABSTRACT_TREE_FOLDER, ROOT_ABSTRACT_FILE,
                      get_abstract_tree_dir)
from ..renderer import render_context
from ..walker import ProjectWalker

console = Console()

_THIRTY_MIN = 30 * 60
_TWO_HOURS = 2 * 60 * 60


def _manage_folder_mode_context(abstract_dir: Path) -> None:
    """Rotate existing context.md and manage the bin/ subfolder.

    Steps:
    1. Delete files in bin/ older than 2 hours.
    2. Move context-*.md files in abstract_dir older than 30 min into bin/.
    3. Rename current context.md with its mtime as timestamp.
    """
    now = time.time()
    bin_dir = abstract_dir / "bin"

    # 1. Clean bin/ — delete files older than 2 hours
    if bin_dir.exists():
        for f in sorted(bin_dir.iterdir()):
            if f.is_file() and (now - f.stat().st_mtime) > _TWO_HOURS:
                f.unlink()

    # 2. Move already-renamed context-*.md files older than 30 min to bin/
    for f in sorted(abstract_dir.glob("context-*.md")):
        if f.is_file() and (now - f.stat().st_mtime) > _THIRTY_MIN:
            bin_dir.mkdir(exist_ok=True)
            f.rename(bin_dir / f.name)

    # 3. Rename current context.md with timestamp based on its mtime
    context_path = abstract_dir / "context.md"
    if context_path.exists():
        mtime = context_path.stat().st_mtime
        timestamp = datetime.fromtimestamp(mtime).strftime("%Y%m%d-%H%M%S")
        renamed = abstract_dir / f"context-{timestamp}.md"
        context_path.rename(renamed)
        # If the renamed file is already older than 30 min, move it to bin/ immediately
        if (now - mtime) > _THIRTY_MIN:
            bin_dir.mkdir(exist_ok=True)
            renamed.rename(bin_dir / renamed.name)


def run_create(root: Path, output: Path | None = None) -> None:
    """Walk directory, apply abstract.yaml config, render context.md."""
    abstract_dir = get_abstract_tree_dir(root)
    folder_mode = abstract_dir != root

    if output:
        output_path = output
    elif folder_mode:
        output_path = abstract_dir / "context.md"
    else:
        output_path = root / "context.md"

    if folder_mode:
        _manage_folder_mode_context(abstract_dir)

    walker = ProjectWalker(root)
    result = walker.walk()

    if not result.files:
        console.print("[yellow]Warning:[/yellow] No files found to include in context.")

    content = render_context(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    console.print(f"[green]Written[/green] {output_path}")
    console.print(f"  Files included: {len(result.files)}")
    console.print(f"  Size: {len(content):,} characters")
