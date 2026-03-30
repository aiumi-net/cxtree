from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

from ..models import (ABSTRACT_FILE, ABSTRACT_TREE_FOLDER, ROOT_ABSTRACT_FILE,
                      get_abstract_tree_dir)

console = Console()


def run_rm(root: Path) -> None:
    """Remove all cxtree-generated artefacts under *root* in a single pass.

    Removed unconditionally (regardless of normal vs. folder mode):
    - ``.abstract-tree/`` folder (entire tree, including rotated context files)
    - ``abstract-tree.yaml`` at project root
    - ``context.md`` at project root
    - All ``abstract.yaml`` child files in subdirectories
    - All ``context.md`` files in subdirectories (split-mode artefacts from
      ``create --max-lines``)
    """
    removed: list[str] = []

    # .abstract-tree/ folder (folder mode)
    abstract_tree_folder = root / ABSTRACT_TREE_FOLDER
    if abstract_tree_folder.exists():
        shutil.rmtree(abstract_tree_folder)
        removed.append(str(abstract_tree_folder) + "/")

    # Root-level abstract-tree.yaml
    abstract_tree_path = root / ROOT_ABSTRACT_FILE
    if abstract_tree_path.exists():
        abstract_tree_path.unlink()
        removed.append(str(abstract_tree_path))

    # Root-level context.md
    root_context = root / "context.md"
    if root_context.exists():
        root_context.unlink()
        removed.append(str(root_context))

    # Child abstract.yaml files in subdirectories
    for abstract_file in sorted(root.rglob(ABSTRACT_FILE)):
        if ABSTRACT_TREE_FOLDER in abstract_file.parts:
            continue
        abstract_file.unlink()
        removed.append(str(abstract_file))

    # context.md files in subdirectories (split-mode artefacts)
    for context_file in sorted(root.rglob("context.md")):
        if ABSTRACT_TREE_FOLDER in context_file.parts:
            continue
        if context_file.parent == root:
            continue  # already handled above
        context_file.unlink()
        removed.append(str(context_file))

    if removed:
        for path in removed:
            console.print(f"[red]Removed[/red] {path}")
        console.print(f"  Total: {len(removed)} item(s) removed")
    else:
        console.print("[yellow]Nothing to remove.[/yellow]")
