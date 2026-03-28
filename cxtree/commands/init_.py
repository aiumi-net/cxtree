from __future__ import annotations

import ast as _ast
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

from ..models import (ABSTRACT_FILE, ABSTRACT_TREE_FOLDER, LEAF_FILE,
                      ROOT_ABSTRACT_FILE, Config)
from ..yaml_io import (_QuotedStr, build_root_abstract, is_root_abstract,
                       load_yaml, save_yaml)

console = Console()

# Dunder methods that are implementation-internal lifecycle hooks and should be skipped
_SKIP_DUNDERS: frozenset[str] = frozenset(
    {
        "__init__",
        "__post_init__",
        "__new__",
        "__del__",
        "__init_subclass__",
        "__class_getitem__",
        "__set_name__",
    }
)

# Extensions to scan for when building ext_found
_SCAN_EXTENSIONS: frozenset[str] = frozenset(
    {
        "py",
        "txt",
        "toml",
        "md",
        "lock",
        "json",
        "Dockerfile",
        "yml",
        "yaml",
        "env",
        "sh",
        "js",
        "ts",
        "tsx",
        "jsx",
        "html",
        "css",
    }
)


def _get_ext(path: Path) -> str | None:
    """Return the extension (without dot) or filename if no extension."""
    if path.suffix:
        return path.suffix.lstrip(".")
    # Files like Dockerfile, .env etc.
    name = path.name
    if name.startswith("."):
        return None
    return name if name in _SCAN_EXTENSIONS else None


# ---------------------------------------------------------------------------
# AST-based docstring extraction
# ---------------------------------------------------------------------------


def _docstring_lines(node: _ast.AST) -> list[_QuotedStr] | None:
    """Extract a docstring from an AST node as a list of quoted lines, or None.

    Returns None when no docstring is present.
    Strips leading/trailing blank lines; preserves internal blank lines.
    """
    raw = _ast.get_docstring(node, clean=True)  # type: ignore[arg-type]
    if not raw:
        return None
    lines = raw.splitlines()
    # Strip leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    # Strip trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None
    return [_QuotedStr(line) for line in lines]


def _build_file_entry(path: Path) -> Any:
    """Parse a Python file and return an abstract-tree.yaml entry value.

    For each top-level class and function:
    - Docstring present  → list of _QuotedStr lines (one per docstring line)
    - No docstring       → "docs" tag (shows code at render time)

    Classes with methods use the long form: {abstract: [...], def: {name: [...]|"docs"}}
    Classes without methods and bare functions use a simple list or "docs".
    Files with no classes or functions return the module docstring list or "docs".
    """
    if path.suffix != ".py":
        return "include"
    try:
        source = path.read_text(encoding="utf-8")
        tree = _ast.parse(source, filename=str(path))
    except Exception:
        return "docs"

    classes: dict[str, Any] = {}
    functions: dict[str, Any] = {}

    for node in tree.body:
        if isinstance(node, _ast.ClassDef):
            class_lines = _docstring_lines(node)
            methods: dict[str, Any] = {}
            for item in node.body:
                if isinstance(item, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    if item.name in _SKIP_DUNDERS:
                        continue
                    m_lines = _docstring_lines(item)
                    methods[item.name] = m_lines if m_lines is not None else "docs"
            if methods:
                classes[node.name] = {
                    "x_abstract": class_lines if class_lines is not None else "docs",
                    "def": methods,
                }
            else:
                classes[node.name] = class_lines if class_lines is not None else "docs"

        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if node.name in _SKIP_DUNDERS:
                continue
            # Top-level functions always use the docs tag (rendered from source)
            functions[node.name] = "docs"

    if not classes and not functions:
        module_lines = _docstring_lines(tree)
        return module_lines if module_lines is not None else "docs"

    entry: dict[str, Any] = {}
    # Add module docstring as x_abstract if present
    module_lines = _docstring_lines(tree)
    if module_lines is not None:
        entry["x_abstract"] = module_lines
    if classes:
        entry["class"] = classes
    if functions:
        entry["def"] = functions
    return entry


def run_init(root: Path, folder: bool = False) -> None:
    """Walk project, discover files, create root abstract-tree.yaml.

    If folder=True, files are placed inside a .abstract-tree/ subdirectory
    which contains a .gitignore that excludes all its contents from git.
    """
    if folder:
        # Delete existing root-level files before switching to folder mode
        for fname in (ROOT_ABSTRACT_FILE, "context.md"):
            root_file = root / fname
            if root_file.exists():
                root_file.unlink()
                console.print(
                    f"[yellow]Deleted[/yellow] existing {root_file} (migrating to folder mode)"
                )
        abstract_dir = root / ABSTRACT_TREE_FOLDER
        abstract_dir.mkdir(exist_ok=True)
        gitignore_path = abstract_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("*\n", encoding="utf-8")
    else:
        # Delete .abstract-tree/ folder when switching back to normal mode
        abstract_tree_folder = root / ABSTRACT_TREE_FOLDER
        if abstract_tree_folder.exists():
            shutil.rmtree(abstract_tree_folder)
            console.print(
                f"[yellow]Deleted[/yellow] {abstract_tree_folder} (switching to normal mode)"
            )
        abstract_dir = root

    abstract_path = abstract_dir / ROOT_ABSTRACT_FILE

    # Load existing config if present (also check the other location for migration)
    existing_data = load_yaml(abstract_path)
    if not existing_data:
        # Check alternate location in case mode changed
        alt_path = (
            (root / ROOT_ABSTRACT_FILE)
            if folder
            else (root / ABSTRACT_TREE_FOLDER / ROOT_ABSTRACT_FILE)
        )
        existing_data = load_yaml(alt_path)
    existing_config: Config | None = None
    if is_root_abstract(existing_data):
        from ..yaml_io import parse_root_abstract

        existing_config, _, _ = parse_root_abstract(existing_data)

    config = existing_config or Config()

    # Default exclude settings
    exclude_startswith = config.exclude_startswith
    exclude_folders = config.exclude_folders

    # Walk and discover
    found_extensions: set[str] = set()
    dir_tree: dict[str, list[str]] = {}  # dir_dot_key -> list of filenames
    root_files: list[str] = []  # files directly in project root

    def _should_skip_dir(name: str) -> bool:
        return (
            any(name.startswith(p) for p in exclude_startswith)
            or name in exclude_folders
            or name == "__pycache__"
        )

    include_extensions = config.include_extensions

    def _is_included(item: Path) -> bool:
        """Return True if this file matches the include extensions list."""
        ext = item.suffix.lstrip(".")
        name = item.name
        return ext in include_extensions or name in include_extensions

    def _walk(directory: Path, dot_prefix: str) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        files_in_dir: list[str] = []
        subdirs: list[Path] = []

        for item in entries:
            name = item.name
            if name in (ABSTRACT_FILE, ROOT_ABSTRACT_FILE, LEAF_FILE):
                continue
            if any(name.startswith(p) for p in exclude_startswith):
                continue
            if item.is_dir():
                if _should_skip_dir(name):
                    continue
                subdirs.append(item)
            elif item.is_file():
                ext = _get_ext(item)
                if ext:
                    found_extensions.add(ext)
                # Only include in abstract-tree if extension matches include list
                if _is_included(item):
                    files_in_dir.append(name)

        if dot_prefix:  # non-root directory: store under dot-notation key
            dir_tree[dot_prefix] = files_in_dir
        else:  # root directory: store files separately
            root_files.extend(files_in_dir)

        for subdir in subdirs:
            name = subdir.name
            new_prefix = f"{dot_prefix}.{name}" if dot_prefix else name
            _walk(subdir, new_prefix)

    _walk(root, "")

    # Build entries dict — directories first (sorted), then root files (sorted)
    entries: dict[str, Any] = {}

    # Subdirectory entries in dot-notation with is_dir: true
    for dot_key in sorted(dir_tree.keys()):
        files = sorted(dir_tree[dot_key])
        dir_abs = root / dot_key.replace(".", "/")
        dir_entry: dict[str, Any] = {"is_dir": True}
        for fname in files:
            dir_entry[fname] = _build_file_entry(dir_abs / fname)
        entries[dot_key] = dir_entry

    # Root-level files after directories (sorted)
    for fname in sorted(root_files):
        entries[fname] = _build_file_entry(root / fname)

    config.ext_found = sorted(found_extensions)
    config.is_flat = True  # init always produces a flat structure

    data = build_root_abstract(config=config, root_tag="docs", entries=entries)

    save_yaml(abstract_path, data)
    if folder:
        console.print(
            f"[green]Created[/green] {abstract_path} [dim](folder mode)[/dim]"
        )
    else:
        console.print(f"[green]Created[/green] {abstract_path}")
    console.print(f"  Extensions found: {', '.join(sorted(found_extensions))}")
    console.print(f"  Directories indexed: {len(dir_tree)}")
