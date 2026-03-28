from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

from ..models import (ABSTRACT_FILE, ABSTRACT_TREE_FOLDER, ROOT_ABSTRACT_FILE,
                      get_abstract_tree_dir)

console = Console()


def run_rm(root: Path) -> None:
    """Remove context.md, abstract-tree.yaml, and all abstract.yaml files.

    In folder mode (.abstract-tree/ exists), the entire .abstract-tree/ directory
    is deleted (including rotated context files and bin/).
    In normal mode, only context.md and abstract-tree.yaml are removed.
    In both modes, all child abstract.yaml files in subdirectories are removed.
    """
    abstract_dir = get_abstract_tree_dir(root)
    folder_mode = abstract_dir != root
    removed: list[str] = []

    if folder_mode:
        # Delete the entire .abstract-tree directory
        shutil.rmtree(abstract_dir)
        removed.append(str(abstract_dir) + "/")
    else:
        # Normal mode: remove specific files
        context_path = abstract_dir / "context.md"
        if context_path.exists():
            context_path.unlink()
            removed.append(str(context_path))

        abstract_tree_path = abstract_dir / ROOT_ABSTRACT_FILE
        if abstract_tree_path.exists():
            abstract_tree_path.unlink()
            removed.append(str(abstract_tree_path))

    # Remove all child abstract.yaml files in subdirectories
    for abstract_file in sorted(root.rglob(ABSTRACT_FILE)):
        if ABSTRACT_TREE_FOLDER in abstract_file.parts:
            continue
        abstract_file.unlink()
        removed.append(str(abstract_file))

    if removed:
        for path in removed:
            console.print(f"[red]Removed[/red] {path}")
        console.print(f"  Total: {len(removed)} item(s) removed")
    else:
        console.print("[yellow]Nothing to remove.[/yellow]")
