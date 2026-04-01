from __future__ import annotations

import ast
import re
from pathlib import Path

from .walker import FileEntry

_CX_RE = re.compile(r"#\s*(?:cxtree|CX)(?:\s+(-\d+))?")

# ---------------------------------------------------------------------------
# Code-mode helpers
# ---------------------------------------------------------------------------


def _classify_docstrings(
    source: str,
) -> tuple[list[tuple[int, int]], set[int]]:
    """Classify all docstrings in *source*.

    Returns:
        skip_ranges — list of (start, end) 1-indexed line ranges to remove.
        protected   — set of 1-indexed line numbers inside *kept* docstrings
                      (those containing the ``# cxtree`` marker).  Lines in
                      this set must not have CX-marker processing applied.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], set()

    lines = source.splitlines()
    skip_ranges: list[tuple[int, int]] = []
    protected: set[int] = set()

    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            continue
        start = first.lineno
        end = first.end_lineno
        if start is None or end is None:
            continue
        doc_text = "\n".join(lines[start - 1 : end])
        if "#cxtree" in doc_text or "# cxtree" in doc_text:
            # Marker present — keep this docstring but shield its lines from
            # the CX-marker regex (the marker text is inside a string literal,
            # not a real directive).
            protected.update(range(start, end + 1))
        else:
            skip_ranges.append((start, end))

    return skip_ranges, protected


def render_code(path: Path) -> str:
    """Render a file in ``--code`` mode.

    For Python files:
    - Docstrings are removed unless the docstring body contains ``# cxtree``.
    - Lines matching ``# cxtree`` / ``# CX`` are removed (except inside
      preserved docstrings, where the text is a literal string, not a marker).
    - Lines matching ``# CX -N`` / ``# cxtree -N`` skip the next N lines,
      replacing them with a single ``# ...`` placeholder.

    Non-Python files are returned as-is (CX markers still apply).
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    lines = source.splitlines(keepends=True)
    skip_lines: set[int] = set()
    protected: set[int] = set()

    if path.suffix == ".py":
        skip_ranges, protected = _classify_docstrings(source)
        for start, end in skip_ranges:
            skip_lines.update(range(start, end + 1))

    result: list[str] = []
    skip_next = 0

    for i, line in enumerate(lines, 1):
        if skip_next > 0:
            skip_next -= 1
            continue
        if i in skip_lines:
            continue

        # Only apply CX markers outside protected (kept) docstrings
        if i not in protected:
            m = _CX_RE.search(line)
            if m:
                indent = line[: len(line) - len(line.lstrip())]
                n_str = m.group(1)
                if n_str:
                    skip_next = abs(int(n_str))
                result.append(f"{indent}# ...\n")
                continue

        result.append(line)

    return "".join(result)


def render_complete(path: Path) -> str:
    """Render a file in ``--complete`` mode: verbatim content."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Language hint
# ---------------------------------------------------------------------------

_LANG_MAP: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "jsx",
    "tsx": "tsx",
    "sh": "bash",
    "bash": "bash",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
    "toml": "toml",
    "md": "markdown",
    "html": "html",
    "css": "css",
    "sql": "sql",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "rb": "ruby",
    "cpp": "cpp",
    "c": "c",
    "cs": "csharp",
    "kt": "kotlin",
    "swift": "swift",
    "php": "php",
}


def _lang(path: Path) -> str:
    return _LANG_MAP.get(path.suffix.lstrip("."), "")


# ---------------------------------------------------------------------------
# File → markdown block
# ---------------------------------------------------------------------------


def _fmt_path(display: str) -> str:
    """Format a slash-separated relative path with spaces: ``a/b/c`` → ``a / b / c``."""
    return " / ".join(display.replace("\\", "/").split("/"))


def render_file_block(path: Path, code_mode: bool, display: str | None = None) -> str:
    """Render a single file to a fenced markdown code block.

    *display* is the already-formatted heading (e.g. ``root / src / utils.py``).
    Falls back to the bare filename when omitted.
    """
    content = render_code(path) if code_mode else render_complete(path)
    lang = _lang(path)
    heading = display if display else path.name
    return f"### {heading}\n\n```{lang}\n{content.rstrip()}\n```\n"


# ---------------------------------------------------------------------------
# ASCII tree helpers (used for context.md header)
# ---------------------------------------------------------------------------


def _ascii_tree(files: list[FileEntry], prefix: str = "") -> str:
    """Build a compact ASCII tree from a flat list of FileEntry."""
    # Build a nested dict
    tree: dict = {}
    for f in files:
        parts = Path(f.rel).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None  # leaf

    lines: list[str] = []
    _render_tree_node(tree, lines, "")
    return "\n".join(lines)


def _render_tree_node(node: dict, lines: list[str], indent: str) -> None:
    keys = sorted(node.keys(), key=lambda k: (node[k] is None, k.lower()))
    for i, key in enumerate(keys):
        connector = "└── " if i == len(keys) - 1 else "├── "
        child = node[key]
        lines.append(f"{indent}{connector}{key}")
        if isinstance(child, dict):
            extension = "    " if i == len(keys) - 1 else "│   "
            _render_tree_node(child, lines, indent + extension)


# ---------------------------------------------------------------------------
# Full context.md rendering
# ---------------------------------------------------------------------------


def render_context(
    files: list[FileEntry],
    code_mode: bool,
    leaf: dict | None = None,
    title: str = "Project Context",
) -> str:
    """Render a complete context.md string.

    *title* is the directory name used as a prefix in every file heading so
    readers always see the full path, e.g. ``app_1 / domain / users / auth.py``.

    *leaf* is the parsed abstract-leaf.yaml for the directory being rendered.
    When a file or subdir key in *leaf* has a non-False string value, that
    summary text is used in place of the actual file content.
    """
    leaf = leaf or {}
    parts: list[str] = [f"# {title}\n"]

    # Tree overview
    if files:
        tree_text = _ascii_tree(files)
        parts.append(f"```\n{tree_text}\n```\n")

    parts.append("---\n")

    def _display(rel: str) -> str:
        """Build the full display path: ``title/rel`` formatted with spaces."""
        full = f"{title}/{rel}" if title and title != "." else rel
        return _fmt_path(full)

    # Group immediate files vs. files under subdirs
    immediate = [f for f in files if "/" not in f.rel]
    by_subdir: dict[str, list[FileEntry]] = {}
    for f in files:
        if "/" in f.rel:
            sub = f.rel.split("/")[0]
            by_subdir.setdefault(sub, []).append(f)

    # Directories first (VS Code explorer order), then immediate files
    for subdir in sorted(by_subdir):
        summary = leaf.get(f"{subdir}/")
        if isinstance(summary, str) and summary.strip():
            parts.append(f"### {_display(subdir + '/')}\n\n{summary.strip()}\n")
        else:
            # Further group by next path component within this subdir (dirs before files)
            sub_imm: list[FileEntry] = []
            sub_by_dir: dict[str, list[FileEntry]] = {}
            for f in by_subdir[subdir]:
                within = f.rel[len(subdir) + 1 :]
                if "/" in within:
                    sub_by_dir.setdefault(within.split("/")[0], []).append(f)
                else:
                    sub_imm.append(f)

            for sub_sub in sorted(sub_by_dir):
                sub_path = f"{subdir}/{sub_sub}"
                sub_summary = leaf.get(f"{sub_path}/")
                if isinstance(sub_summary, str) and sub_summary.strip():
                    parts.append(
                        f"### {_display(sub_path + '/')}\n\n{sub_summary.strip()}\n"
                    )
                else:
                    for f in sub_by_dir[sub_sub]:
                        summary_f = leaf.get(f.rel)
                        if summary_f is None:
                            summary_f = leaf.get(Path(f.rel).name)
                        if isinstance(summary_f, str) and summary_f.strip():
                            parts.append(
                                f"### {_display(f.rel)}\n\n{summary_f.strip()}\n"
                            )
                        else:
                            parts.append(
                                render_file_block(f.path, code_mode, _display(f.rel))
                            )

            for f in sorted(sub_imm, key=lambda x: x.rel.lower()):
                summary_f = leaf.get(f.rel)
                if summary_f is None:
                    summary_f = leaf.get(Path(f.rel).name)
                if isinstance(summary_f, str) and summary_f.strip():
                    parts.append(f"### {_display(f.rel)}\n\n{summary_f.strip()}\n")
                else:
                    parts.append(render_file_block(f.path, code_mode, _display(f.rel)))

    for f in sorted(immediate, key=lambda x: x.rel.lower()):
        summary = leaf.get(f.rel)
        if summary is None:
            summary = leaf.get(Path(f.rel).name)
        if isinstance(summary, str) and summary.strip():
            parts.append(f"### {_display(f.rel)}\n\n{summary.strip()}\n")
        else:
            parts.append(render_file_block(f.path, code_mode, _display(f.rel)))

    return "\n".join(parts)


def count_lines(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)
