from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.tree import Tree

from ..models import Config, get_abstract_tree_dir
from ..yaml_io import is_root_abstract, load_yaml, parse_root_abstract

console = Console()


def _build_rich_tree(
    directory: Path,
    tree_node: Tree,
    config: Config,
) -> None:
    """Recursively add directory contents to a Rich Tree node."""
    try:
        entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return

    for item in entries:
        name = item.name

        # Skip entries whose name starts with any excluded prefix
        if any(name.startswith(s) for s in config.exclude_startswith):
            continue

        if item.is_dir():
            if name in config.exclude_folders:
                continue
            child_node = tree_node.add(f"[bold orange1]{name}[/bold orange1]")
            _build_rich_tree(item, child_node, config)
        else:
            if item.suffix == ".py":
                tree_node.add(f"[bold blue]{name}[/bold blue]")
            else:
                tree_node.add(f"[white]{name}[/white]")


def run_tree(root: Path) -> None:
    """Print a colored directory tree of the project using Rich."""
    abstract_dir = get_abstract_tree_dir(root)
    abstract_path = abstract_dir / "abstract-tree.yaml"

    data = load_yaml(abstract_path)
    if data and is_root_abstract(data):
        config, _, _ = parse_root_abstract(data)
    else:
        config = Config()

    root_tree = Tree(f"[bold red]{root.name.upper()}[/bold red]")
    _build_rich_tree(root, root_tree, config)
    console.print(root_tree)
