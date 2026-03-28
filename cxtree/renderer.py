from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .source import render_python_file
from .walker import FileEntry, WalkResult

# ---------------------------------------------------------------------------
# Directory tree rendering
# ---------------------------------------------------------------------------


def _collect_tree_paths(result: WalkResult) -> list[Path]:
    """Collect all unique directories and files needed for the tree."""
    paths: set[Path] = set()
    for fe in result.files:
        # Add the file itself and all ancestor directories up to (not including) root
        paths.add(fe.path)
        for parent in fe.path.parents:
            if parent == result.root or not str(parent).startswith(str(result.root)):
                break
            paths.add(parent)
    return sorted(paths)


def _render_tree(result: WalkResult) -> str:
    """Render an ASCII directory tree for the files in the walk result."""
    root = result.root
    root_name = root.name

    # Build a nested dict representing the tree
    tree: dict[str, Any] = {}
    for fe in result.files:
        if fe.is_dir_entry:
            continue  # directory summaries are not shown in the file tree
        try:
            rel = fe.path.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    lines: list[str] = [f"{root_name}/"]
    _render_tree_node(tree, lines, prefix="")
    return "\n".join(lines) + "\n"


def _render_tree_node(node: dict[str, Any], lines: list[str], prefix: str) -> None:
    items = sorted(node.keys(), key=lambda k: (bool(node[k]), k))
    for i, name in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        child = node[name]
        if child:  # directory
            lines.append(f"{prefix}{connector}{name}/")
            extension = "    " if is_last else "│   "
            _render_tree_node(child, lines, prefix + extension)
        else:  # file
            lines.append(f"{prefix}{connector}{name}")


# ---------------------------------------------------------------------------
# File content rendering
# ---------------------------------------------------------------------------


def _apply_empty_line_policy(content: str, rm_empty_lines: bool) -> str:
    """Apply empty-line normalisation to rendered file content.

    rm_empty_lines=False → collapse sequences of 2+ blank lines to a single blank line.
    rm_empty_lines=True  → source.py already stripped blanks within symbols and added
                           exactly 1 blank line between them; just normalise any stray 2+
                           blank lines to 1.
    """
    # In both cases: collapse 3+ consecutive newlines (= 2+ blank lines) to 1 blank line
    return re.sub(r"\n{3,}", "\n\n", content)


def _render_file_content(
    fe: FileEntry, rm_empty_lines: bool = False, rm_empty_lines_docs: bool = False
) -> str | None:
    """Render a single file entry to a string, or None if nothing to show."""
    if fe.tag == "exclude":
        return None

    if fe.text_replacement is not None:
        return f"# {fe.text_replacement}"

    path = fe.path
    suffix = path.suffix.lower()

    if suffix == ".py":
        content = render_python_file(
            path, fe.file_cfg, fe.tag, rm_empty_lines, rm_empty_lines_docs
        )
        if not content:
            return None
        content = content.rstrip("\n")
    else:
        # Non-Python files: include as-is
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if not content.strip():
            return None
        content = content.rstrip("\n")

    return _apply_empty_line_policy(content, rm_empty_lines)


def _lang_hint(path: Path) -> str:
    """Return a markdown code fence language hint."""
    ext = path.suffix.lstrip(".")
    mapping = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "tsx",
        "jsx": "jsx",
        "toml": "toml",
        "yaml": "yaml",
        "yml": "yaml",
        "json": "json",
        "md": "markdown",
        "sh": "bash",
        "bash": "bash",
        "txt": "",
        "env": "",
        "Dockerfile": "dockerfile",
    }
    name = path.name
    if name in mapping:
        return mapping[name]
    return mapping.get(ext, ext)


# ---------------------------------------------------------------------------
# Full context.md rendering
# ---------------------------------------------------------------------------


def render_context(result: WalkResult) -> str:
    """Render the full context.md content from a WalkResult."""
    sections: list[str] = []

    sections.append("# Project Context\n")

    # Directory tree
    sections.append("## Directory Tree\n")
    tree_str = _render_tree(result)
    sections.append(f"```\n{tree_str}\n```\n")

    # File sections
    rm = result.config.rm_empty_lines
    rm_docs = result.config.rm_empty_lines_docs
    for fe in result.files:
        content = _render_file_content(fe, rm, rm_docs)
        if content is None:
            continue

        try:
            rel = fe.path.relative_to(result.root)
            rel_str = "/".join(rel.parts)
        except ValueError:
            rel_str = str(fe.path)

        if fe.is_dir_entry:
            sections.append(f"## {rel_str}/\n")
            sections.append(f"```\n{content}\n```\n")
        else:
            lang = _lang_hint(fe.path)
            sections.append(f"## {rel_str}\n")
            sections.append(f"```{lang}\n{content}\n```\n")

    return "\n".join(sections)
