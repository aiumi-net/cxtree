from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.tree import Tree

from ..config import ABSTRACT_TREE_FILE, CONTEXT_TREE_DIR, Config
from ..renderer import count_lines, render_context
from ..walker import FileEntry, walk_dir
from ..yaml_io import load_config, load_leaf

console = Console()


# ---------------------------------------------------------------------------
# Line-count helpers
# ---------------------------------------------------------------------------


def _compute_dir_line_counts(project_root: Path, config: Config) -> dict[Path, int]:
    """Return a mapping of directory Path → rendered line count."""
    all_files = walk_dir(project_root, config)

    # Collect all unique ancestor dirs
    dirs: set[Path] = {project_root}
    for fe in all_files:
        p = (project_root / fe.rel).parent
        while True:
            dirs.add(p)
            if p == project_root:
                break
            p = p.parent

    counts: dict[Path, int] = {}
    for d in dirs:
        sub_files = [
            FileEntry(project_root / f.rel, f.rel)
            for f in all_files
            if (project_root / f.rel).is_relative_to(d)
        ]
        if not sub_files:
            continue
        leaf = load_leaf(d)
        content = render_context(sub_files, code_mode=False, leaf=leaf)
        counts[d] = count_lines(content)

    return counts


def _should_show_pct(
    directory: Path,
    project_root: Path,
    dir_lines: dict[Path, int],
    max_lines: int,
) -> bool:
    count = dir_lines.get(directory)
    if count is None or count > max_lines:
        return False
    if directory == project_root:
        return True
    parent_count = dir_lines.get(directory.parent)
    return parent_count is not None and parent_count > max_lines


def _is_leaf_dir(directory: Path, dir_lines: dict[Path, int]) -> bool:
    return not any(p.parent == directory for p in dir_lines if p != directory)


def _pct_label(line_count: int, max_lines: int, name_len: int = 0) -> str:
    pct = line_count / max_lines * 100
    color = (
        "green"
        if pct <= 80
        else "yellow" if pct <= 90 else "red" if pct <= 100 else "magenta"
    )
    n_dots = max(2, 80 - name_len)
    dots = "." * n_dots
    return f" {dots} [ [bold {color}]{pct:.0f}%[/bold {color}] ]"


# ---------------------------------------------------------------------------
# Tree rendering
# ---------------------------------------------------------------------------


def _build_rich_tree(
    directory: Path,
    tree_node: Tree,
    config: Config,
    dir_lines: dict[Path, int] | None,
    max_lines: int,
    project_root: Path,
) -> None:
    try:
        entries = sorted(
            directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
        )
    except PermissionError:
        return

    for item in entries:
        name = item.name

        if any(name.startswith(s) for s in config.exclude_startswith):
            continue

        if item.is_dir():
            if name in config.exclude_folders:
                continue
            label = f"[bold orange1]{name}[/bold orange1]"
            if dir_lines is not None and max_lines > 0:
                count = dir_lines.get(item)
                if _should_show_pct(item, project_root, dir_lines, max_lines):
                    label += _pct_label(dir_lines[item], max_lines, len(name))
                elif (
                    count is not None
                    and count > max_lines
                    and _is_leaf_dir(item, dir_lines)
                ):
                    label += _pct_label(count, max_lines, len(name))
            child_node = tree_node.add(label)
            _build_rich_tree(
                item, child_node, config, dir_lines, max_lines, project_root
            )
        else:
            ext = item.suffix
            if ext == ".py":
                tree_node.add(f"[bold blue]{name}[/bold blue]")
            elif ext in {".yaml", ".yml", ".toml", ".json"}:
                tree_node.add(f"[bold cyan]{name}[/bold cyan]")
            else:
                tree_node.add(f"[white]{name}[/white]")


def run_tree(root: Path, max_lines: int) -> None:
    """Print a coloured directory tree with optional line-budget percentages."""
    config = load_config(root / CONTEXT_TREE_DIR) or load_config(root) or Config()

    dir_lines = _compute_dir_line_counts(root, config)

    root_label = f"[bold red]{root.name.upper()}[/bold red]"
    root_count = dir_lines.get(root)
    if _should_show_pct(root, root, dir_lines, max_lines):
        root_label += _pct_label(dir_lines[root], max_lines, len(root.name))
    elif (
        root_count is not None
        and root_count > max_lines
        and _is_leaf_dir(root, dir_lines)
    ):
        root_label += _pct_label(root_count, max_lines, len(root.name))

    rich_tree = Tree(root_label)
    _build_rich_tree(root, rich_tree, config, dir_lines, max_lines, root)
    console.print(rich_tree)
