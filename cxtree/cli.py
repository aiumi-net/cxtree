from __future__ import annotations

from pathlib import Path

import click

from .commands.create_ import run_create
from .commands.rm_ import run_rm
from .commands.tree_ import run_tree
from .config import DEFAULT_N


@click.group()
@click.version_option()
def main() -> None:
    """cxtree — generate focused LLM context files from your project."""


# ---------------------------------------------------------------------------
# tree
# ---------------------------------------------------------------------------


@main.command("tree")
@click.option(
    "-n",
    "--max-lines",
    default=DEFAULT_N,
    show_default=True,
    help="Line budget used for percentage display.",
)
def cmd_tree(max_lines: int) -> None:
    """Print a coloured directory tree with line-budget percentages."""
    root = Path.cwd()
    run_tree(root, max_lines)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@main.command("create")
@click.option(
    "-n",
    "--max-lines",
    default=None,
    type=int,
    help=(
        "Maximum lines per context.md before splitting.  "
        "Saved to abstract-tree.yaml; omit on subsequent runs to reuse."
    ),
)
@click.option(
    "--code / --complete",
    "code_mode",
    default=False,
    help=(
        "--complete (default): verbatim file content.  "
        "--code: strip docstrings (unless marked with # cxtree) and apply CX markers."
    ),
)
@click.option(
    "-f",
    "--folder",
    "folder_mode",
    is_flag=True,
    default=False,
    help="Store context files inside .context-tree/ with rotation and cleanup.",
)
def cmd_create(max_lines: int | None, code_mode: bool, folder_mode: bool) -> None:
    """Generate context.md file(s) from the current directory."""
    root = Path.cwd()
    run_create(root, max_lines, code_mode, folder_mode)


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


@main.command("rm")
def cmd_rm() -> None:
    """Remove all cxtree-generated files.

    abstract-leaf.yaml files that contain user-written summaries are kept.
    """
    root = Path.cwd()
    run_rm(root)
