from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ABSTRACT_FILE = "abstract.yaml"  # child config files in subdirectories
ROOT_ABSTRACT_FILE = "abstract-tree.yaml"  # root config file
ABSTRACT_TREE_FOLDER = (
    ".abstract-tree"  # folder mode: contains abstract-tree.yaml + context.md
)
LEAF_FILE = "abstract-leaf.yaml"  # highest-priority flat key→description overrides


def get_abstract_tree_dir(root: Path) -> Path:
    """Return the directory containing abstract-tree.yaml.

    In folder mode (.abstract-tree/ exists with abstract-tree.yaml inside),
    returns root/.abstract-tree. Otherwise returns root.
    """
    folder = root / ABSTRACT_TREE_FOLDER
    if (folder / ROOT_ABSTRACT_FILE).exists():
        return folder
    return root


VALID_TAGS: frozenset[str] = frozenset({"code", "docs", "include", "exclude"})

DEFAULT_TAG = "include"


@dataclass
class Config:
    """Project-level configuration from the cxtree: block."""

    include_extensions: list[str] = field(default_factory=lambda: ["py"])
    ext_found: list[str] = field(default_factory=list)
    exclude_startswith: list[str] = field(default_factory=lambda: [".", "__"])
    exclude_folders: list[str] = field(
        default_factory=lambda: [".venv", "node_modules", "__pycache__"]
    )
    rm_empty_lines: bool = (
        False  # True → remove all blank lines; False → collapse multiple to one
    )
    rm_empty_lines_docs: bool = (
        True  # True → remove blank lines from doc-only rendering
    )
    is_flat: bool = True  # True → use only root abstract-tree.yaml; False → leaf mode

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        is_flat: bool = True,
        ext_found: list[str] | None = None,
    ) -> Config:
        # Support both x_-prefixed (current) and legacy unprefixed keys
        include_block = (
            data.get("include", {}) if isinstance(data.get("include"), dict) else {}
        )
        if "x_extensions" in include_block:
            include_extensions = include_block["x_extensions"]
        else:
            include_extensions = include_block.get("extensions", ["py"])

        exclude = data.get("exclude", {}) or {}
        exclude_startswith = (
            exclude["x_startswith"]
            if "x_startswith" in exclude
            else exclude.get("startswith", [".", "__"])
        )
        exclude_folders = (
            exclude["x_folders"]
            if "x_folders" in exclude
            else exclude.get("folders", [".venv", "node_modules", "__pycache__"])
        )
        rm_empty_lines = bool(
            data["x_rm_empty_lines"]
            if "x_rm_empty_lines" in data
            else data.get("rm_empty_lines", False)
        )
        rm_empty_lines_docs = bool(
            data["x_rm_empty_lines_docs"]
            if "x_rm_empty_lines_docs" in data
            else data.get("rm_empty_lines_docs", True)
        )
        return cls(
            include_extensions=include_extensions,
            ext_found=ext_found or [],
            exclude_startswith=exclude_startswith,
            exclude_folders=exclude_folders,
            rm_empty_lines=rm_empty_lines,
            rm_empty_lines_docs=rm_empty_lines_docs,
            is_flat=is_flat,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_rm_empty_lines": self.rm_empty_lines,
            "x_rm_empty_lines_docs": self.rm_empty_lines_docs,
            "include": {"x_extensions": self.include_extensions},
            "exclude": {
                "x_startswith": self.exclude_startswith,
                "x_folders": self.exclude_folders,
            },
        }


def parse_entry_value(
    value: Any,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    """Parse a YAML entry value into (tag, text, children_dict).

    Returns:
        (tag, text, children):
          - tag: one of VALID_TAGS or None
          - text: replacement text string or None
          - children: dict of child entries or None (for symbol-level dicts)
    """
    if value is None:
        return None, None, None

    if isinstance(value, str):
        if value in VALID_TAGS:
            return value, None, None
        # Text replacement
        return None, value, None

    if isinstance(value, list):
        # All items must be strings — multiline text
        parts = [str(item) for item in value]
        return None, "\n".join(parts), None

    if isinstance(value, dict):
        # Could be:
        #   - directory/file entry with abstract:/x_abstract: key → tag, children
        #   - file-level symbol dict (class:/def: keys)
        #   - symbol long-form dict (x_abstract:/abstract: + def: keys)
        abstract_key: str | None = None
        if "x_abstract" in value:
            abstract_key = "x_abstract"
        elif "abstract" in value:
            abstract_key = "abstract"

        if abstract_key is not None:
            abstract_val = value[abstract_key]
            tag = (
                abstract_val
                if isinstance(abstract_val, str) and abstract_val in VALID_TAGS
                else None
            )
            children = {
                k: v for k, v in value.items() if k not in ("abstract", "x_abstract")
            }
            return tag, None, children if children else None
        # Plain children dict (class:/def: or method dicts)
        return None, None, value

    return None, None, None
