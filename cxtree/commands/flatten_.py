from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from ..models import ABSTRACT_FILE, ROOT_ABSTRACT_FILE, get_abstract_tree_dir
from ..yaml_io import (build_root_abstract, is_child_abstract,
                       is_root_abstract, load_yaml, parse_root_abstract,
                       save_yaml)

console = Console()


def _update_x_is_flat_in_parent(parent_abstract: Path, dir_name: str) -> None:
    """Set x_is_flat: true for dir_name entry in a parent child abstract."""
    data = load_yaml(parent_abstract)
    if not data or dir_name not in data:
        return
    entry = data[dir_name]
    if not isinstance(entry, dict):
        return
    entry["x_is_flat"] = True
    save_yaml(parent_abstract, data)


def _dir_key_from_path(root: Path, directory: Path) -> str:
    """Convert an absolute directory path to a dot-notation key like 'src.auth'."""
    rel = directory.relative_to(root)
    return ".".join(rel.parts)


def _depth(directory: Path, root: Path) -> int:
    rel = directory.relative_to(root)
    return len(rel.parts)


def _collect_child_abstracts(
    root: Path, config_exclude_startswith: list[str], config_exclude_folders: list[str]
) -> list[tuple[Path, dict[str, Any]]]:
    """Walk the tree and collect all valid child abstract.yaml files."""
    results: list[tuple[Path, dict[str, Any]]] = []

    def _walk(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return

        for item in entries:
            name = item.name
            if not item.is_dir():
                continue
            if any(name.startswith(p) for p in config_exclude_startswith):
                continue
            if name in config_exclude_folders:
                continue

            child_abstract = item / ABSTRACT_FILE
            if child_abstract.exists():
                data = load_yaml(child_abstract)
                depth = _depth(item, root)
                if data and is_child_abstract(data, depth):
                    results.append((item, data))

            _walk(item)

    _walk(root)
    return results


def run_flatten(root: Path, subtree: str | None = None) -> None:
    """Collect all child abstract.yaml files and merge into root.

    If subtree is given (e.g. 'domain' or 'domain/users'), only the child
    abstracts under that path are merged; others remain untouched.
    """
    abstract_path = get_abstract_tree_dir(root) / ROOT_ABSTRACT_FILE
    data = load_yaml(abstract_path)

    if not data or not is_root_abstract(data):
        console.print(
            f"[red]Error:[/red] No root abstract-tree.yaml found at {abstract_path}"
        )
        return

    config, root_tag, root_entries = parse_root_abstract(data)

    # Collect all child abstracts, then optionally filter to a subtree
    all_child_abstracts = _collect_child_abstracts(
        root, config.exclude_startswith, config.exclude_folders
    )

    if subtree:
        subtree_path = root / subtree.replace(".", "/").rstrip("/")
        child_abstracts = [
            (d, cd)
            for d, cd in all_child_abstracts
            if d == subtree_path or subtree_path in d.parents
        ]
        if not child_abstracts:
            console.print(
                f"[yellow]No child abstract.yaml files found under {subtree_path}.[/yellow]"
            )
            return
    else:
        child_abstracts = all_child_abstracts
        if not child_abstracts:
            console.print("[yellow]No child abstract.yaml files found.[/yellow]")
            return

    # Track which child abstracts are being deleted so we don't update a parent that's also going away
    deleted_abstract_paths: set[Path] = {d / ABSTRACT_FILE for d, _ in child_abstracts}

    # Merge child file entries into root entries
    _SKIP_KEYS = frozenset({"abstract-depth", "parent-dirs"})
    new_entries: dict[str, Any] = dict(root_entries)
    deleted: list[Path] = []

    for dir_path, child_data in child_abstracts:
        dir_key = _dir_key_from_path(root, dir_path)
        file_entries: dict[str, Any] = {
            k: v
            for k, v in child_data.items()
            if k not in _SKIP_KEYS
            and not (isinstance(v, dict) and v.get("is_dir") is True)
        }

        if not file_entries:
            # No actual entries — skip
            continue

        # Get existing root entry for this directory (may have x_abstract and is_dir keys)
        existing = new_entries.get(dir_key, {})
        if isinstance(existing, dict):
            # Support both x_abstract (current) and legacy abstract key
            existing_abstract = existing.get("x_abstract", existing.get("abstract"))
        else:
            existing_abstract = None

        # Build merged entry — preserve is_dir: true for dot-notation format
        merged: dict[str, Any] = {"is_dir": True}
        if existing_abstract is not None:
            merged["x_abstract"] = existing_abstract
        merged.update(file_entries)

        new_entries[dir_key] = merged

        # Delete child file
        child_path = dir_path / ABSTRACT_FILE
        try:
            child_path.unlink()
            deleted.append(child_path)
        except OSError as exc:
            console.print(
                f"[yellow]Warning:[/yellow] Could not delete {child_path}: {exc}"
            )
            continue

        # Update parent's child abstract to mark this dir as x_is_flat: true
        parent_path = dir_path.parent
        parent_abstract = parent_path / ABSTRACT_FILE
        if (
            parent_path != root
            and parent_abstract not in deleted_abstract_paths
            and parent_abstract.exists()
        ):
            _update_x_is_flat_in_parent(parent_abstract, dir_path.name)

    # Determine is_flat: True only when no child abstracts remain anywhere
    if subtree:
        remaining = _collect_child_abstracts(
            root, config.exclude_startswith, config.exclude_folders
        )
        config.is_flat = not bool(remaining)
    else:
        config.is_flat = True

    new_root_data = build_root_abstract(
        config=config, root_tag=root_tag, entries=new_entries
    )
    save_yaml(abstract_path, new_root_data)

    console.print(f"[green]Updated[/green] root {abstract_path.name}")
    for p in deleted:
        console.print(f"[red]Deleted[/red] child {p}")
    console.print(f"  Child files merged and deleted: {len(deleted)}")
