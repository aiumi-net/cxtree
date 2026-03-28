from __future__ import annotations

from pathlib import Path

import click

from .commands.create_ import run_create
from .commands.flatten_ import run_flatten
from .commands.init_ import run_init
from .commands.leaf_ import run_leaf
from .commands.rm_ import run_rm
from .commands.tree_ import run_tree


@click.group()
@click.version_option(package_name="cxtree")
def main() -> None:
    """cxtree: generate focused LLM context files from your project."""


@main.command("init")
@click.option(
    "--root",
    "-r",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Project root directory.",
)
@click.option(
    "--folder",
    is_flag=True,
    default=False,
    help="Store abstract-tree.yaml and context.md inside a .abstract-tree/ subfolder.",
)
def cmd_init(root: Path, folder: bool) -> None:
    """Walk project and create root abstract-tree.yaml with discovered paths."""
    run_init(root.resolve(), folder=folder)


@main.command("create")
@click.option(
    "--root",
    "-r",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Project root directory.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(path_type=Path),
    help="Output file path (default: <root>/context.md).",
)
def cmd_create(root: Path, output: Path | None) -> None:
    """Generate context.md from abstract-tree.yaml configuration."""
    resolved_root = root.resolve()
    resolved_output = output.resolve() if output else None
    run_create(resolved_root, resolved_output)


@main.command("rm")
@click.argument(
    "path",
    default=".",
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
def cmd_rm(path: Path) -> None:
    """Remove context.md, abstract-tree.yaml, and all child abstract.yaml files.

    PATH defaults to the current directory. Pass a subdirectory to target a
    project rooted there (e.g. domain/users where abstract-tree.yaml lives).
    """
    run_rm(path.resolve())


@main.command("leafs")
@click.option(
    "--root",
    "-r",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Project root directory.",
)
def cmd_leaf(root: Path) -> None:
    """Split root abstract-tree.yaml into per-directory child abstract.yaml files."""
    run_leaf(root.resolve())


@main.command("tree")
@click.argument(
    "path",
    default=".",
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
def cmd_tree(path: Path) -> None:
    """Show a colored directory tree of the project."""
    run_tree(path.resolve())


@main.command("flatten")
@click.option(
    "--root",
    "-r",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Project root directory.",
)
@click.argument("path", default=None, required=False)
def cmd_flatten(root: Path, path: str | None) -> None:
    """Merge child abstract.yaml files back into root abstract-tree.yaml.

    PATH optionally limits the operation to a subtree, e.g. 'domain' or
    'domain.users'. Only child abstracts under that path are merged; all
    others remain untouched.
    """
    run_flatten(root.resolve(), subtree=path)
