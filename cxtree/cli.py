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
@click.option(
    "--default",
    "-d",
    "default_tag",
    type=click.Choice(["docs", "code", "include"]),
    default="docs",
    show_default=True,
    help="Default tag inherited down the tree (docs/code/include).",
)
@click.option(
    "--docs",
    "explicit_tag",
    flag_value="docs",
    help=(
        "Set 'docs' explicitly on every entry in the tree. "
        "Docstrings are pulled from source at render time instead of being embedded."
    ),
)
@click.option(
    "--code",
    "explicit_tag",
    flag_value="code",
    help=(
        "Set 'code' explicitly on every entry in the tree. "
        "Renders code bodies; docstrings are stripped at render time."
    ),
)
@click.option(
    "--include",
    "explicit_tag",
    flag_value="include",
    help=(
        "Set 'include' explicitly on every entry in the tree. "
        "Full source (code + docstrings) is rendered for every symbol."
    ),
)
def cmd_init(
    root: Path, folder: bool, default_tag: str, explicit_tag: str | None
) -> None:
    """Walk project and create root abstract-tree.yaml with discovered paths."""
    run_init(
        root.resolve(),
        folder=folder,
        default_tag=default_tag,
        explicit_tag=explicit_tag,
    )


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
@click.option(
    "--max-lines",
    "-n",
    "max_lines",
    default=3000,
    show_default=True,
    type=int,
    help=(
        "Maximum lines per context.md. When exceeded the file is not written at the "
        "current level; instead one context.md per subfolder is created recursively "
        "until the limit is met or leaf directories are reached."
    ),
)
@click.option(
    "--docs",
    "explicit_tag",
    flag_value="docs",
    help=(
        "Re-init with 'docs' tag before creating: docstrings are pulled from source "
        "at render time. Equivalent to running init --docs then create."
    ),
)
@click.option(
    "--code",
    "explicit_tag",
    flag_value="code",
    help=(
        "Re-init with 'code' tag before creating: code bodies are rendered, "
        "docstrings stripped. Equivalent to running init --code then create."
    ),
)
@click.option(
    "--include",
    "explicit_tag",
    flag_value="include",
    help=(
        "Re-init with 'include' tag before creating: full source (code + docstrings) "
        "is rendered. Equivalent to running init --include then create."
    ),
)
def cmd_create(
    root: Path, output: Path | None, max_lines: int, explicit_tag: str | None
) -> None:
    """Generate context.md from abstract-tree.yaml configuration.

    Pass --docs, --code, or --include to override the effective tag on every
    file at render time without modifying any configuration files.
    """
    resolved_root = root.resolve()
    resolved_output = output.resolve() if output else None
    run_create(
        resolved_root, resolved_output, max_lines=max_lines, explicit_tag=explicit_tag
    )


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
@click.option(
    "--max-lines",
    "-n",
    "max_lines",
    default=3000,
    show_default=True,
    type=int,
    help=(
        "Line budget used to compute the fill-percentage shown next to each "
        "directory. A percentage is shown only where create --max-lines N would "
        "write a context.md (fits in budget, parent overflows). "
        "green ≤ 80 %, yellow ≤ 90 %, red > 90 %."
    ),
)
def cmd_tree(path: Path, max_lines: int) -> None:
    """Show a colored directory tree of the project."""
    run_tree(path.resolve(), max_lines=max_lines)


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
