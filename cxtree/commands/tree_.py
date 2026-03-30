from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.tree import Tree

from ..models import Config, get_abstract_tree_dir
from ..renderer import render_context
from ..walker import FileEntry, ProjectWalker, WalkResult
from ..yaml_io import is_root_abstract, load_yaml, parse_root_abstract

console = Console()


# ---------------------------------------------------------------------------
# Line-count helpers for --max-lines percentage display
# ---------------------------------------------------------------------------


def _files_for_dir(files: list[FileEntry], directory: Path) -> list[FileEntry]:
    """Return every FileEntry whose rendered content belongs to *directory*.

    A regular file at path P belongs to every ancestor directory D (P != D).
    A dir-entry at path P (summary for that directory) belongs to P's parent
    and all ancestors, but not to P itself.
    """
    return [
        fe for fe in files if fe.path != directory and fe.path.is_relative_to(directory)
    ]


def _compute_dir_line_counts(result: WalkResult) -> dict[Path, int]:
    """Return a mapping of directory → render line count for every directory
    that appears as an ancestor of at least one file in *result*.

    The count reflects exactly how many lines ``render_context`` would produce
    for a context.md scoped to that directory.
    """
    root = result.root

    # Collect all unique ancestor directories (including root itself)
    dirs: set[Path] = {root}
    for fe in result.files:
        p = fe.path.parent  # for both files and dir-entries
        while p.is_relative_to(root):
            dirs.add(p)
            if p == root:
                break
            p = p.parent

    counts: dict[Path, int] = {}
    for d in dirs:
        sub_files = _files_for_dir(result.files, d)
        if not sub_files:
            continue
        sub = WalkResult(root=root, config=result.config, files=sub_files)
        content = render_context(sub)
        counts[d] = len(content.splitlines())

    return counts


def _should_show_pct(
    directory: Path,
    project_root: Path,
    dir_lines: dict[Path, int],
    max_lines: int,
) -> bool:
    """Return True if *directory* is a split target that would receive a complete context.md.

    A directory shows its percentage when both conditions hold:
    1. Its own content fits within the budget (≤ max_lines).
       Overflowing directories are split further and do not get shown.
    2. Its parent overflows (> max_lines), which is what causes the split that
       gives this directory its own context.md — OR it is the project root
       (no parent above it).
    """
    count = dir_lines.get(directory)
    if count is None or count > max_lines:
        return False
    if directory == project_root:
        return True
    parent_count = dir_lines.get(directory.parent)
    return parent_count is not None and parent_count > max_lines


def _is_leaf_dir(directory: Path, dir_lines: dict[Path, int]) -> bool:
    """Return True if *directory* has no subdirectory entries in dir_lines.

    Leaf directories receive a single context.md regardless of line count
    because there is nothing to split into.
    """
    return not any(p.parent == directory for p in dir_lines if p != directory)


def _pct_label(line_count: int, max_lines: int, name_len: int = 0) -> str:
    """Return a Rich-markup percentage label with adaptive dot padding.

    The dot section compensates for *name_len* so the bracket ``[ XX% ]``
    appears at a consistent column regardless of the folder name length.
    Each dot unit is three characters (`` . ``).  A minimum of two units is
    always used so the label never looks cramped.

    Colors: green ≤ 80 %, yellow ≤ 90 %, red ≤ 100 %, magenta > 100 %
    (over-budget leaf — consider splitting the module).
    """
    pct = line_count / max_lines * 100
    if pct > 100:
        color = "magenta"
    elif pct > 90:
        color = "red"
    elif pct > 80:
        color = "yellow"
    else:
        color = "green"
    # Target: name + dots ≈ 30 display chars.  Each " . " = 3 chars.
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
    """Recursively add directory contents to a Rich Tree node."""
    try:
        entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
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
                    # Leaf dir that exceeds budget — show >100% to hint at refactoring
                    label += _pct_label(count, max_lines, len(name))
            child_node = tree_node.add(label)
            _build_rich_tree(
                item, child_node, config, dir_lines, max_lines, project_root
            )
        else:
            if item.suffix == ".py":
                tree_node.add(f"[bold blue]{name}[/bold blue]")
            else:
                tree_node.add(f"[white]{name}[/white]")


def run_tree(root: Path, max_lines: int = 3000) -> None:
    """Print a colored directory tree of the project using Rich."""
    abstract_dir = get_abstract_tree_dir(root)
    abstract_path = abstract_dir / "abstract-tree.yaml"

    data = load_yaml(abstract_path)
    if data and is_root_abstract(data):
        config, _, _ = parse_root_abstract(data)
    else:
        config = Config()

    # Pre-compute line counts for percentage display
    walker = ProjectWalker(root)
    walk_result = walker.walk()
    dir_lines = _compute_dir_line_counts(walk_result)

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

    root_tree = Tree(root_label)
    _build_rich_tree(root, root_tree, config, dir_lines, max_lines, root)
    console.print(root_tree)
