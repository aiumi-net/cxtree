from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from ..config import (ABSTRACT_TREE_FILE, CONTEXT_FILE, CONTEXT_TREE_DIR,
                      SUBCONTEXT_FILE, Config)
from ..renderer import count_lines, render_context
from ..walker import FileEntry, walk_dir
from ..yaml_io import ensure_leaf, load_config, load_leaf, save_abstract_tree

console = Console()


# ---------------------------------------------------------------------------
# Extension scanner
# ---------------------------------------------------------------------------


def _scan_extensions(root: Path, config: Config) -> list[str]:
    """Walk the project (no extension filter) and return sorted unique extensions found."""
    found: set[str] = set()
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel_parts = item.relative_to(root).parts
        if any(part in config.exclude_folders for part in rel_parts):
            continue
        if any(part.startswith(tuple(config.exclude_startswith)) for part in rel_parts):
            continue
        ext = item.suffix.lstrip(".")
        found.add(ext if ext else item.name)
    return sorted(found, key=str.lower)


# ---------------------------------------------------------------------------
# Leaf collector
# ---------------------------------------------------------------------------


def _collect_leaves(dir_path: Path, config: Config, _prefix: str = "") -> dict:
    """Recursively load abstract-leaf.yaml from *dir_path* and all subdirs.

    Keys are prefixed with the relative path so the merged dict can be used
    when rendering a context file that spans multiple subdirectories.

    Example: ``domain/abstract-leaf.yaml`` has ``users/: 'Users...'``
    → merged dict contains ``domain/users/: 'Users...'``.
    """
    result: dict = {}
    local = load_leaf(dir_path) or {}
    for k, v in local.items():
        result[_prefix + k] = v

    for sub in dir_path.iterdir():
        if not sub.is_dir():
            continue
        if sub.name in config.exclude_folders:
            continue
        if any(sub.name.startswith(p) for p in config.exclude_startswith):
            continue
        sub_prefix = _prefix + sub.name + "/"
        result.update(_collect_leaves(sub, config, sub_prefix))

    return result


# ---------------------------------------------------------------------------
# Folder-mode helpers
# ---------------------------------------------------------------------------


def _setup_context_tree_dir(root: Path) -> Path:
    """Create .context-tree/ with .gitignore if needed, clean old bin/ entries."""
    ctx_dir = root / CONTEXT_TREE_DIR
    ctx_dir.mkdir(exist_ok=True)

    gitignore = ctx_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")

    bin_dir = ctx_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    _cleanup_bin(bin_dir)

    return ctx_dir


def _cleanup_bin(bin_dir: Path, max_age_hours: int = 2) -> None:
    """Remove timestamped subdirectories (and stray files) older than max_age_hours."""
    now = datetime.now(tz=timezone.utc).timestamp()
    for item in bin_dir.iterdir():
        if (now - item.stat().st_mtime) > max_age_hours * 3600:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()


def _rotate_all_contexts(ctx_dir: Path) -> None:
    """Move all existing *.md files in ctx_dir to a single timestamped bin/ subfolder."""
    existing = [f for f in ctx_dir.iterdir() if f.is_file() and f.suffix == ".md"]
    if not existing:
        return
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    ts_dir = ctx_dir / "bin" / ts
    ts_dir.mkdir(parents=True, exist_ok=True)
    for f in existing:
        shutil.move(str(f), ts_dir / f.name)


# ---------------------------------------------------------------------------
# Destination helpers
# ---------------------------------------------------------------------------


def _context_dest(dir_path: Path, project_root: Path, ctx_dir: Path | None) -> Path:
    """Return the Path where the context file for *dir_path* should be written.

    Normal mode:
        root  → <root>/context.md
        other → <dir>/_context.md

    Folder mode (flat inside .context-tree/):
        root  → .context-tree/context.md
        other → .context-tree/<rel_encoded>_context.md
                e.g. domain/users → .context-tree/domain_users_context.md
    """
    is_root = dir_path == project_root
    if ctx_dir is None:
        return dir_path / (CONTEXT_FILE if is_root else SUBCONTEXT_FILE)
    # Folder mode — flat
    if is_root:
        return ctx_dir / CONTEXT_FILE
    rel = str(dir_path.relative_to(project_root))
    flat = rel.replace("/", "_").replace("\\", "_")
    return ctx_dir / f"{flat}_context.md"


def _overflow_ref(
    subdir: str, dir_path: Path, project_root: Path, ctx_dir: Path | None
) -> str:
    """Return the display path used in overflow refs inside context.md."""
    if ctx_dir is None:
        return f"{subdir}/{SUBCONTEXT_FILE}"
    sub_full = dir_path / subdir
    rel = str(sub_full.relative_to(project_root))
    flat = rel.replace("/", "_").replace("\\", "_")
    # All folder-mode context files live in the same .context-tree/ dir,
    # so links between them are just bare filenames (no path prefix needed).
    return f"{flat}_context.md"


def _write_context(
    dir_path: Path,
    project_root: Path,
    content: str,
    ctx_dir: Path | None,
) -> None:
    dest = _context_dest(dir_path, project_root, ctx_dir)
    dest.write_text(content, encoding="utf-8")
    console.print(f"[green]Written[/green] {dest.relative_to(project_root)}")


# ---------------------------------------------------------------------------
# Abstract-tree structure builder
# ---------------------------------------------------------------------------


def _build_abstract_tree(
    project_root: Path,
    all_files: list[FileEntry],
    ctx_dir: Path | None,
) -> dict[str, object]:
    """Build the flat tree dict for abstract-tree.yaml.

    Each key is a directory path in slash-notation.  The value is either a
    list of immediate file names (no overflow) or ``_context.md`` (overflow).
    Root-level files are stored under the ``_root`` key.
    """
    tree: dict[str, object] = {}

    root_files = [Path(f.rel).name for f in all_files if "/" not in f.rel]
    if root_files:
        tree["_root"] = root_files

    all_dir_rels: set[str] = set()
    for f in all_files:
        parts = Path(f.rel).parts
        for i in range(len(parts) - 1):
            all_dir_rels.add("/".join(parts[: i + 1]))

    covered: set[str] = set()

    for dir_rel in sorted(all_dir_rels, key=lambda d: (d.count("/"), d)):
        if any(dir_rel == c or dir_rel.startswith(c + "/") for c in covered):
            continue

        dir_path = project_root / dir_rel

        # Check if overflow happened (subdir context file exists)
        if ctx_dir is None:
            overflowed = (dir_path / SUBCONTEXT_FILE).exists()
        else:
            flat = dir_rel.replace("/", "_").replace("\\", "_")
            overflowed = (ctx_dir / f"{flat}_context.md").exists()

        if overflowed:
            tree[dir_rel] = SUBCONTEXT_FILE
            covered.add(dir_rel)
        else:
            prefix = dir_rel + "/"
            imm_files = [
                Path(f.rel).name
                for f in all_files
                if f.rel.startswith(prefix) and "/" not in f.rel[len(prefix) :]
            ]
            if imm_files:
                tree[dir_rel] = imm_files

    return tree


# ---------------------------------------------------------------------------
# Core recursive create
# ---------------------------------------------------------------------------


def _create_dir(
    dir_path: Path,
    project_root: Path,
    config: Config,
    code_mode: bool,
    ctx_dir: Path | None,
) -> None:
    """Recursively create context files for *dir_path*.

    If all files fit within ``config.n`` lines, one file is written here
    (context.md at root, _context.md in subdirs).
    Otherwise each immediate sub-directory gets its own context file (recursed),
    and a summary is written for this level with root-level files + overflow refs.
    """
    files = walk_dir(dir_path, config, dir_path)
    if not files:
        return

    # Local leaf: used for overflow detection (keys relative to dir_path).
    # Merged leaf: includes all subdir abstract-leaf.yaml with prefixed keys,
    # so render_context can find summaries at any depth.
    local_leaf = load_leaf(dir_path) or {}
    merged_leaf = _collect_leaves(dir_path, config)
    rel = str(dir_path.relative_to(project_root))
    title = project_root.name if rel == "." else rel

    full_content = render_context(files, code_mode, merged_leaf, title)

    imm_files = [f for f in files if "/" not in f.rel]
    imm_dirs = sorted({f.rel.split("/")[0] for f in files if "/" in f.rel})
    is_root = dir_path == project_root

    if count_lines(full_content) <= config.n:
        _write_context(dir_path, project_root, full_content, ctx_dir)
        if not is_root:
            ensure_leaf(dir_path, [f.rel for f in imm_files], imm_dirs)
        return

    # Overflow — split by subdir.
    # Subdirs with a leaf summary are kept inline (no separate _context.md).
    # Subdirs without a summary are recursed into.
    summarized_dirs = {
        d
        for d in imm_dirs
        if isinstance(local_leaf.get(f"{d}/"), str)
        and str(local_leaf.get(f"{d}/", "")).strip()
    }
    unsummarized_dirs = [d for d in imm_dirs if d not in summarized_dirs]

    for subdir in unsummarized_dirs:
        _create_dir(dir_path / subdir, project_root, config, code_mode, ctx_dir)

    # Build overflow refs only for dirs that got their own _context.md
    ref_lines = [
        f"- *[{_overflow_ref(d, dir_path, project_root, ctx_dir)}]"
        f"({_overflow_ref(d, dir_path, project_root, ctx_dir)})*"
        for d in unsummarized_dirs
    ]
    refs_block = "\n".join(ref_lines)

    # Include summarized subdirs in the render so leaf summaries appear inline.
    # Files from summarized subdirs are included so render_context sees them in by_subdir.
    summarized_files = [
        f for f in files if "/" in f.rel and f.rel.split("/")[0] in summarized_dirs
    ]
    inline_files = imm_files + summarized_files
    inline_content = render_context(inline_files, code_mode, local_leaf, title)
    root_content = (
        inline_content.rstrip() + ("\n\n" + refs_block if refs_block else "") + "\n"
    )
    _write_context(dir_path, project_root, root_content, ctx_dir)
    if not is_root:
        ensure_leaf(dir_path, [f.rel for f in imm_files], imm_dirs)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_create(
    root: Path,
    n: int | None,
    code_mode: bool,
    folder_mode: bool,
) -> None:
    ctx_tree_dir = root / CONTEXT_TREE_DIR

    # Auto-activate folder mode when .context-tree/ already exists
    if ctx_tree_dir.exists():
        folder_mode = True

    # Load config from .context-tree/ (folder mode) or root (normal mode)
    existing_config = load_config(ctx_tree_dir) or load_config(root)
    config = existing_config or Config()
    if n is not None:
        config.n = n

    ctx_dir: Path | None = None
    if folder_mode:
        ctx_dir = _setup_context_tree_dir(root)
        _rotate_all_contexts(ctx_dir)  # batch-rotate before any new writes

    config.extensions_found = _scan_extensions(root, config)

    _create_dir(root, root, config, code_mode, ctx_dir)

    all_files = walk_dir(root, config)
    tree = _build_abstract_tree(root, all_files, ctx_dir)

    # abstract-tree.yaml lives at root (normal) or in .context-tree/ (folder mode)
    abstract_tree_dir = ctx_dir if ctx_dir is not None else root
    save_abstract_tree(abstract_tree_dir, config, tree)
    console.print(
        f"[green]Written[/green] {(abstract_tree_dir / ABSTRACT_TREE_FILE).relative_to(root)}"
    )
