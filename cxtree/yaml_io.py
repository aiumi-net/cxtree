from __future__ import annotations

from pathlib import Path

import yaml

from .config import ABSTRACT_LEAF_FILE, ABSTRACT_TREE_FILE, Config

# ---------------------------------------------------------------------------
# Custom YAML dumper — indents list items properly
# ---------------------------------------------------------------------------


class _IndentDumper(yaml.Dumper):
    """Dumper that indents sequence items under their parent key."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # type: ignore[override]
        return super().increase_indent(flow=flow, indentless=False)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=_IndentDumper,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


# ---------------------------------------------------------------------------
# abstract-tree.yaml
# ---------------------------------------------------------------------------


def load_config(root: Path) -> Config | None:
    """Load Config from abstract-tree.yaml at *root*. Returns None if absent."""
    data = load_yaml(root / ABSTRACT_TREE_FILE)
    if not data or "cxtree" not in data:
        return None
    return Config.from_dict(data["cxtree"])


def save_abstract_tree(root: Path, config: Config, tree: dict[str, object]) -> None:
    """Write abstract-tree.yaml with config header + tree entries."""
    data: dict = {"cxtree": config.to_dict()}
    data.update(tree)
    save_yaml(root / ABSTRACT_TREE_FILE, data)


def load_abstract_tree_structure(root: Path) -> dict[str, object]:
    """Return just the tree entries (non-cxtree keys) from abstract-tree.yaml."""
    data = load_yaml(root / ABSTRACT_TREE_FILE)
    return {k: v for k, v in data.items() if k != "cxtree"}


# ---------------------------------------------------------------------------
# abstract-leaf.yaml
# ---------------------------------------------------------------------------


def load_leaf(directory: Path) -> dict[str, object]:
    return load_yaml(directory / ABSTRACT_LEAF_FILE)


def save_leaf(directory: Path, data: dict[str, object]) -> None:
    save_yaml(directory / ABSTRACT_LEAF_FILE, data)


def ensure_leaf(
    directory: Path, file_names: list[str], subdir_names: list[str]
) -> None:
    """Create or update abstract-leaf.yaml in *directory*.

    Existing entries (including user-written summaries) are never
    reformatted.  Only missing keys are added — either by creating the
    file from scratch or by appending new ``key: false`` lines so the
    rest of the file is left byte-for-byte unchanged.
    """
    leaf_path = directory / ABSTRACT_LEAF_FILE
    existing = load_leaf(directory)

    all_keys = list(file_names) + [f"{n}/" for n in subdir_names]
    missing = [k for k in all_keys if k not in existing]

    if not missing and leaf_path.exists():
        return  # nothing to do — file is already complete

    if not leaf_path.exists():
        # Create from scratch
        data: dict[str, object] = {k: False for k in all_keys}
        if data:
            save_leaf(directory, data)
        return

    # Append only the missing keys to preserve existing formatting
    lines = "".join(f"{k}: false\n" for k in missing)
    with open(leaf_path, "a", encoding="utf-8") as f:
        f.write(lines)
