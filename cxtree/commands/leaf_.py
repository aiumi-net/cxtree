from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from ..models import ABSTRACT_FILE, ROOT_ABSTRACT_FILE, get_abstract_tree_dir
from ..yaml_io import (build_root_abstract, is_root_abstract, load_yaml,
                       parse_root_abstract, save_yaml)
from .init_ import run_init

console = Console()


def _is_dir_entry(key: str, value: Any) -> bool:
    """Return True if this entry represents a directory (old slash or new dot notation)."""
    if key.endswith("/"):
        return True
    return isinstance(value, dict) and value.get("is_dir") is True


def _depth_of_dir_key(dir_key: str) -> int:
    """Return the depth of a directory key (slash or dot notation)."""
    if dir_key.endswith("/"):
        stripped = dir_key.rstrip("/")
        return stripped.count("/") + 1
    # Dot notation: "domain" → 1, "domain.users" → 2
    return dir_key.count(".") + 1


def _dir_path_from_key(root: Path, dir_key: str) -> Path:
    """Convert a dir key (slash or dot notation) to an absolute Path."""
    if dir_key.endswith("/"):
        return root / Path(dir_key.rstrip("/"))
    # Dot notation: "domain.users" → root/domain/users
    return root / Path(dir_key.replace(".", "/"))


_NON_FILE_ENTRY_KEYS = frozenset(
    {"abstract", "x_abstract", "is_dir", "x_hard_abstract"}
)


def _has_file_entries(value: Any) -> bool:
    """Return True if a directory entry value contains file-level entries."""
    if not isinstance(value, dict):
        return False
    file_keys = {
        k for k in value.keys() if not k.endswith("/") and k not in _NON_FILE_ENTRY_KEYS
    }
    return bool(file_keys)


def _merge_entries_from_child_abstracts(
    root: Path, entries: dict[str, Any]
) -> tuple[dict[str, Any], set[str], dict[str, Any]]:
    """Augment root entries with file entries from existing child abstracts.

    In leaf re-run mode, the root abstract has no file entries (they live in
    child abstracts). This function loads those child abstracts and adds the
    file entries back into the root entries dict so the normal processing
    loop can work on them.

    Additionally detects directories marked in their parent's child abstract with:
    - ``x_is_flat: true`` — flatten back to root level
    - ``x_hard_abstract: "off"`` — feature inactive, ignored (normal processing)
    - ``x_hard_abstract: <text>`` — active description with absolute priority,
      no file entries; child abstract will be deleted

    Returns:
        augmented_entries: root entries with file entries added from child abstracts
        flatten_back: set of dir keys that should be kept inline in root
        hard_abstract: dir_key -> description for dirs with an active x_hard_abstract
    """
    flatten_back: set[str] = set()
    hard_abstract: dict[str, Any] = {}

    # Pre-scan: collect x_is_flat and active x_hard_abstract from all parent child abstracts.
    # x_hard_abstract: "off" means the feature is inactive — ignored entirely.
    for key, value in entries.items():
        if not _is_dir_entry(key, value):
            continue
        dir_path = _dir_path_from_key(root, key)
        child_path = dir_path / ABSTRACT_FILE
        if not child_path.exists():
            continue
        child_data = load_yaml(child_path)
        if not child_data:
            continue

        for k, v in child_data.items():
            if not (isinstance(v, dict) and v.get("is_dir") is True):
                continue
            sub_path = dir_path / k
            try:
                rel = sub_path.relative_to(root)
                sub_key = ".".join(rel.parts)
            except ValueError:
                continue

            if v.get("x_is_flat") is True:
                flatten_back.add(sub_key)

            x_hard = v.get("x_hard_abstract")
            if x_hard is not None:
                val_str = str(x_hard).strip().strip('"').strip()
                if val_str != "off":
                    # Active description: normalize and store
                    hard_abstract[sub_key] = val_str

    # Build augmented entries
    augmented: dict[str, Any] = {}
    for key, value in entries.items():
        if not _is_dir_entry(key, value):
            augmented[key] = value
            continue

        # hard_abstract: keep with description only, no file entries
        if key in hard_abstract:
            augmented[key] = {"is_dir": True, "x_hard_abstract": hard_abstract[key]}
            continue

        dir_path = _dir_path_from_key(root, key)
        child_path = dir_path / ABSTRACT_FILE
        if not child_path.exists():
            augmented[key] = value
            continue

        child_data = load_yaml(child_path)
        if not child_data:
            augmented[key] = value
            continue

        # Extract file entries from child abstract
        _SKIP = frozenset({"abstract-depth", "parent-dirs"})
        file_entries = {
            k: v
            for k, v in child_data.items()
            if k not in _SKIP and not (isinstance(v, dict) and v.get("is_dir") is True)
        }

        if file_entries:
            base = dict(value) if isinstance(value, dict) else {"is_dir": True}
            augmented[key] = {**base, **file_entries}
        else:
            augmented[key] = value

    return augmented, flatten_back, hard_abstract


def run_leaf(root: Path) -> None:
    """Split flat root abstract.yaml into per-directory child files.

    When called on a project already in leaf mode (is_flat: false), re-runs
    the split. Directories with ``x_is_flat: true`` set in their parent's
    child abstract are flattened back to the root level instead of receiving
    their own child abstract.
    """
    abstract_dir = get_abstract_tree_dir(root)
    abstract_path = abstract_dir / ROOT_ABSTRACT_FILE

    if not abstract_path.exists():
        console.print(
            "[yellow]No abstract-tree.yaml found — running init first...[/yellow]"
        )
        run_init(root)
        abstract_dir = get_abstract_tree_dir(root)
        abstract_path = abstract_dir / ROOT_ABSTRACT_FILE

    data = load_yaml(abstract_path)

    if not data or not is_root_abstract(data):
        console.print(
            f"[red]Error:[/red] No root abstract-tree.yaml found at {abstract_path}"
        )
        return

    config, root_tag, entries = parse_root_abstract(data)

    # If re-running (was already in leaf mode): load file entries from existing
    # child abstracts and detect x_is_flat / x_hard_abstract directives
    flatten_back: set[str] = set()
    hard_abstract: dict[str, Any] = {}
    if not config.is_flat:
        entries, flatten_back, hard_abstract = _merge_entries_from_child_abstracts(
            root, entries
        )

    # Directories that will have their own child abstract (have files, not flatten_back)
    dirs_with_own_abstract: set[str] = {
        key
        for key, value in entries.items()
        if _is_dir_entry(key, value)
        and _has_file_entries(value)
        and key not in flatten_back
    }

    new_root_entries: dict[str, Any] = {}
    child_files_created: list[Path] = []
    child_files_deleted: list[Path] = []

    for key, value in entries.items():
        if not _is_dir_entry(key, value):
            # Not a directory entry — keep as-is in root
            new_root_entries[key] = value
            continue

        # x_hard_abstract active + x_is_flat: true — keep description only, delete child abstract
        if key in hard_abstract and key in flatten_back:
            new_root_entries[key] = value  # {is_dir: true, x_hard_abstract: desc}
            dir_path = _dir_path_from_key(root, key)
            child_path = dir_path / ABSTRACT_FILE
            if child_path.exists():
                child_path.unlink()
                child_files_deleted.append(child_path)
            continue

        if not _has_file_entries(value):
            # No file entries — keep as-is
            new_root_entries[key] = value
            continue

        # Has file entries
        if key in flatten_back:
            # User set x_is_flat: true → keep inline in root (partial flatten back)
            new_root_entries[key] = value
            # Delete the now-redundant child abstract for this directory
            dir_path = _dir_path_from_key(root, key)
            child_path = dir_path / ABSTRACT_FILE
            if child_path.exists():
                child_path.unlink()
                child_files_deleted.append(child_path)
            continue

        # Normal case: create a child abstract for this directory
        if isinstance(value, dict):
            abstract_tag = value.get("x_abstract", value.get("abstract"))
            file_entries: dict[str, Any] = {
                k: v
                for k, v in value.items()
                if k not in ("abstract", "x_abstract", "is_dir") and not k.endswith("/")
            }
            sub_dir_entries: dict[str, Any] = {
                k: v for k, v in value.items() if k.endswith("/")
            }
        else:
            abstract_tag = None
            file_entries = {}
            sub_dir_entries = {}

        dir_path = _dir_path_from_key(root, key)
        depth = _depth_of_dir_key(key)
        rel_parts = dir_path.relative_to(root).parts
        parent_dirs = list(rel_parts)

        # Immediate subdirectories to list in the child abstract header.
        # Directories in flatten_back are going back to root, so we skip them here.
        child_dir_section: dict[str, Any] = {}
        for other_key, other_value in entries.items():
            if not _is_dir_entry(other_key, other_value):
                continue
            if other_key in flatten_back:
                continue  # this subdir is being flattened back to root
            other_path = _dir_path_from_key(root, other_key)
            try:
                rel = other_path.relative_to(dir_path)
            except ValueError:
                continue
            if len(rel.parts) != 1:
                continue  # only immediate children
            sub_name = rel.parts[0]
            sub_entry: dict[str, Any] = {"is_dir": True}
            if other_key in dirs_with_own_abstract:
                sub_entry["x_is_flat"] = False
                sub_entry["x_hard_abstract"] = (
                    "off"  # placeholder: user replaces to activate
                )
            child_dir_section[sub_name] = sub_entry

        child_data: dict[str, Any] = {"abstract-depth": depth}
        child_data["parent-dirs"] = parent_dirs
        if child_dir_section:
            child_data.update(child_dir_section)
        child_data.update(file_entries)

        child_path = dir_path / ABSTRACT_FILE
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            console.print(f"[red]Error creating directory {dir_path}: {exc}[/red]")
            continue

        save_yaml(child_path, child_data)
        child_files_created.append(child_path)

        # Root keeps directory key with is_dir + abstract tag (+ any sub-dir entries)
        root_dir_val: dict[str, Any] = {"is_dir": True}
        if abstract_tag is not None:
            root_dir_val["x_abstract"] = abstract_tag
        root_dir_val.update(sub_dir_entries)
        new_root_entries[key] = root_dir_val

    # is_flat: True only when no child abstracts remain
    config.is_flat = not bool(child_files_created)

    new_root_data = build_root_abstract(
        config=config, root_tag=root_tag, entries=new_root_entries
    )
    save_yaml(abstract_path, new_root_data)

    console.print(f"[green]Updated[/green] root {abstract_path}")
    for p in child_files_created:
        console.print(f"[green]Created[/green] child {p}")
    for p in child_files_deleted:
        console.print(f"[yellow]Deleted[/yellow] child (flattened back) {p}")
    console.print(f"  Child files created: {len(child_files_created)}")
