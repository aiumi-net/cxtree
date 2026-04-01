from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

from ..config import (ABSTRACT_LEAF_FILE, ABSTRACT_TREE_FILE, CONTEXT_FILE,
                      CONTEXT_TREE_DIR, SUBCONTEXT_FILE)
from ..yaml_io import load_leaf

console = Console()


def _leaf_is_clean(path: Path) -> bool:
    """Return True if all values in abstract-leaf.yaml are False (no user summaries)."""
    data = load_leaf(path.parent)
    if not data:
        return True
    return all(v is False for v in data.values())


def run_rm(root: Path) -> None:
    """Remove all cxtree-generated artefacts under *root*.

    Always removed:
    - ``.context-tree/`` folder
    - ``abstract-tree.yaml`` at project root
    - ``context.md`` at root and in all sub-directories

    Conditionally removed:
    - ``abstract-leaf.yaml`` — only if every value is ``false``
      (i.e. no user-written summaries present).
    """
    removed: list[str] = []

    def _rm(path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(str(path.relative_to(root)))

    # .context-tree/ folder (also contains abstract-tree.yaml in folder mode)
    ctx_dir = root / CONTEXT_TREE_DIR
    if ctx_dir.exists():
        _rm(ctx_dir)

    # abstract-tree.yaml at root (normal mode)
    abstract_tree = root / ABSTRACT_TREE_FILE
    if abstract_tree.exists():
        _rm(abstract_tree)

    # context.md (root) and _context.md (subdirs)
    for pattern in (CONTEXT_FILE, SUBCONTEXT_FILE):
        for ctx_file in sorted(root.rglob(pattern)):
            if CONTEXT_TREE_DIR in ctx_file.parts:
                continue
            _rm(ctx_file)

    # abstract-leaf.yaml — only if clean (all values false)
    for leaf_file in sorted(root.rglob(ABSTRACT_LEAF_FILE)):
        if CONTEXT_TREE_DIR in leaf_file.parts:
            continue
        if _leaf_is_clean(leaf_file):
            _rm(leaf_file)
        else:
            rel = str(leaf_file.relative_to(root))
            console.print(f"[yellow]Kept[/yellow]   {rel}  (has user summaries)")

    if removed:
        for r in removed:
            console.print(f"[red]Removed[/red] {r}")
        console.print(f"  Total: {len(removed)} item(s) removed")
    else:
        console.print("[yellow]Nothing to remove.[/yellow]")
