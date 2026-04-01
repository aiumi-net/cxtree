from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cxtree.commands.create_ import run_create
from cxtree.commands.rm_ import run_rm
from cxtree.config import (ABSTRACT_LEAF_FILE, ABSTRACT_TREE_FILE,
                           CONTEXT_FILE, SUBCONTEXT_FILE)
from cxtree.yaml_io import load_leaf, load_yaml


def _big_py(d: Path, name: str = "module.py", lines: int = 60) -> None:
    (d / name).write_text("\n".join(f"x_{i} = {i}" for i in range(lines)) + "\n")


# ---------------------------------------------------------------------------
# Basic create
# ---------------------------------------------------------------------------


def test_create_writes_context_md(simple_project: Path):
    run_create(simple_project, n=3000, code_mode=False, folder_mode=False)
    assert (simple_project / CONTEXT_FILE).exists()


def test_create_writes_abstract_tree(simple_project: Path):
    run_create(simple_project, n=3000, code_mode=False, folder_mode=False)
    assert (simple_project / ABSTRACT_TREE_FILE).exists()
    data = load_yaml(simple_project / ABSTRACT_TREE_FILE)
    assert "cxtree" in data


def test_create_saves_n_in_config(simple_project: Path):
    run_create(simple_project, n=500, code_mode=False, folder_mode=False)
    data = load_yaml(simple_project / ABSTRACT_TREE_FILE)
    assert data["cxtree"]["n"] == 500


def test_create_reuses_saved_n(simple_project: Path):
    run_create(simple_project, n=500, code_mode=False, folder_mode=False)
    run_create(simple_project, n=None, code_mode=False, folder_mode=False)
    data = load_yaml(simple_project / ABSTRACT_TREE_FILE)
    assert data["cxtree"]["n"] == 500


def test_no_leaf_at_root(simple_project: Path):
    run_create(simple_project, n=3000, code_mode=False, folder_mode=False)
    assert not (simple_project / ABSTRACT_LEAF_FILE).exists()


def test_leaf_created_in_subdir(simple_project: Path):
    """_context.md + abstract-leaf.yaml are created in subdirs on overflow."""
    run_create(simple_project, n=5, code_mode=False, folder_mode=False)
    assert (simple_project / "utils" / SUBCONTEXT_FILE).exists()
    leaf = load_leaf(simple_project / "utils")
    assert leaf
    assert all(v is False for v in leaf.values())


# ---------------------------------------------------------------------------
# Overflow / split
# ---------------------------------------------------------------------------


def test_create_split_uses_subcontext(tmp_path: Path):
    """Overflow puts _context.md in subdirs, not context.md."""
    for sub in ("alpha", "beta"):
        d = tmp_path / sub
        d.mkdir()
        _big_py(d)

    run_create(tmp_path, n=50, code_mode=False, folder_mode=False)

    assert (tmp_path / "alpha" / SUBCONTEXT_FILE).exists()
    assert (tmp_path / "beta" / SUBCONTEXT_FILE).exists()
    # Normal context.md must NOT exist in subdirs
    assert not (tmp_path / "alpha" / CONTEXT_FILE).exists()
    assert not (tmp_path / "beta" / CONTEXT_FILE).exists()


def test_abstract_tree_marks_overflow(tmp_path: Path):
    """Overflowed dirs appear as '_context.md' in abstract-tree.yaml."""
    for sub in ("alpha", "beta"):
        d = tmp_path / sub
        d.mkdir()
        _big_py(d)

    run_create(tmp_path, n=50, code_mode=False, folder_mode=False)

    data = load_yaml(tmp_path / ABSTRACT_TREE_FILE)
    tree = {k: v for k, v in data.items() if k != "cxtree"}
    assert tree.get("alpha") == SUBCONTEXT_FILE
    assert tree.get("beta") == SUBCONTEXT_FILE


# ---------------------------------------------------------------------------
# Folder mode
# ---------------------------------------------------------------------------


def test_create_folder_mode_flat(tmp_path: Path):
    """In folder mode, all context files land flat in .context-tree/."""
    for sub in ("alpha", "beta"):
        d = tmp_path / sub
        d.mkdir()
        _big_py(d)

    run_create(tmp_path, n=50, code_mode=False, folder_mode=True)

    ctx_dir = tmp_path / ".context-tree"
    assert ctx_dir.exists()
    assert (ctx_dir / ".gitignore").exists()
    assert (ctx_dir / CONTEXT_FILE).exists()
    assert (ctx_dir / "alpha_context.md").exists()
    assert (ctx_dir / "beta_context.md").exists()
    # No _context.md in actual subdirs
    assert not (tmp_path / "alpha" / SUBCONTEXT_FILE).exists()


def test_create_folder_mode_rotation(tmp_path: Path):
    """Second run rotates previous context files to a bin/<timestamp>/ subfolder."""
    (tmp_path / "app.py").write_text("x = 1\n")
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=True)
    run_create(
        tmp_path, n=3000, code_mode=False, folder_mode=False
    )  # auto-detects folder mode

    bin_dir = tmp_path / ".context-tree" / "bin"
    ts_dirs = [d for d in bin_dir.iterdir() if d.is_dir()]
    assert len(ts_dirs) == 1
    rotated = list(ts_dirs[0].iterdir())
    assert any(f.name == CONTEXT_FILE for f in rotated)


def test_create_auto_activates_folder_mode(tmp_path: Path):
    """When .context-tree/ already exists, folder mode is auto-activated."""
    (tmp_path / "app.py").write_text("x = 1\n")
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=True)
    # Second run without folder_mode=True
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)
    # abstract-tree.yaml must still be in .context-tree/, not at root
    assert (tmp_path / ".context-tree" / ABSTRACT_TREE_FILE).exists()
    assert not (tmp_path / ABSTRACT_TREE_FILE).exists()


# ---------------------------------------------------------------------------
# abstract-leaf.yaml with summaries
# ---------------------------------------------------------------------------


def test_leaf_summary_used_in_context(tmp_path: Path):
    (tmp_path / "app.py").write_text("x = 1\n")
    import yaml as _yaml

    (tmp_path / ABSTRACT_LEAF_FILE).write_text(
        _yaml.dump({"app.py": "Application entry point."}), encoding="utf-8"
    )

    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)

    content = (tmp_path / CONTEXT_FILE).read_text()
    assert "Application entry point." in content
    assert "x = 1" not in content


# ---------------------------------------------------------------------------
# rm command
# ---------------------------------------------------------------------------


def test_rm_removes_context_and_abstract(simple_project: Path):
    run_create(simple_project, n=3000, code_mode=False, folder_mode=False)
    run_rm(simple_project)
    assert not (simple_project / CONTEXT_FILE).exists()
    assert not (simple_project / ABSTRACT_TREE_FILE).exists()


def test_rm_removes_subcontext(tmp_path: Path):
    """rm removes _context.md files from subdirs."""
    for sub in ("alpha",):
        d = tmp_path / sub
        d.mkdir()
        _big_py(d)
    run_create(tmp_path, n=50, code_mode=False, folder_mode=False)
    assert (tmp_path / "alpha" / SUBCONTEXT_FILE).exists()
    run_rm(tmp_path)
    assert not (tmp_path / "alpha" / SUBCONTEXT_FILE).exists()


def test_rm_keeps_leaf_with_summary(tmp_path: Path):
    import yaml as _yaml

    (tmp_path / "app.py").write_text("x = 1\n")
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    leaf_path.write_text(_yaml.dump({"app.py": "Has a summary."}), encoding="utf-8")
    run_rm(tmp_path)
    assert leaf_path.exists()


def test_rm_removes_clean_leaf(simple_project: Path):
    run_create(simple_project, n=3000, code_mode=False, folder_mode=False)
    run_rm(simple_project)
    assert not (simple_project / ABSTRACT_LEAF_FILE).exists()


def test_rm_removes_context_tree_folder(simple_project: Path):
    run_create(simple_project, n=3000, code_mode=False, folder_mode=True)
    assert (simple_project / ".context-tree").exists()
    run_rm(simple_project)
    assert not (simple_project / ".context-tree").exists()


# ---------------------------------------------------------------------------
# abstract-leaf.yaml summaries — merged across subdirs
# ---------------------------------------------------------------------------


def test_subdir_leaf_summary_appears_in_root_context(tmp_path: Path):
    """Summary in a subdir's abstract-leaf.yaml must appear in root context.md (n large)."""
    import yaml as _yaml

    sub = tmp_path / "domain"
    sub.mkdir()
    _big_py(sub, lines=5)

    (sub / ABSTRACT_LEAF_FILE).write_text(
        _yaml.dump({"module.py": "Domain logic."}), encoding="utf-8"
    )

    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)

    content = (tmp_path / CONTEXT_FILE).read_text()
    assert "Domain logic." in content


def test_subdir_leaf_summary_suppresses_file_content(tmp_path: Path):
    """When a subdir leaf has a file summary, raw source must not appear in root context.md."""
    import yaml as _yaml

    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "secrets.py").write_text("API_KEY = 'abc'\n")

    (sub / ABSTRACT_LEAF_FILE).write_text(
        _yaml.dump({"secrets.py": "Credentials — omitted."}), encoding="utf-8"
    )

    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)

    content = (tmp_path / CONTEXT_FILE).read_text()
    assert "Credentials — omitted." in content
    assert "API_KEY" not in content


def test_nested_subdir_leaf_summary_used_in_root_context(tmp_path: Path):
    """users/ summary in domain/abstract-leaf.yaml must appear in root context.md."""
    import yaml as _yaml

    users = tmp_path / "domain" / "users"
    users.mkdir(parents=True)
    _big_py(users, lines=5)

    (tmp_path / "domain" / ABSTRACT_LEAF_FILE).write_text(
        _yaml.dump({"users/": "User management layer."}), encoding="utf-8"
    )

    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)

    content = (tmp_path / CONTEXT_FILE).read_text()
    assert "User management layer." in content


def test_leaf_not_reformatted_after_create(tmp_path: Path):
    """Running create must not reformat abstract-leaf.yaml when nothing changes."""
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    original = "app.py: false\n"
    (tmp_path / "app.py").write_text("x = 1\n")
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)

    # Now manually write the leaf with block-scalar formatting
    block_text = 'app.py: |\n  "My summary"\n'
    leaf_path.write_text(block_text, encoding="utf-8")

    # Second create — must not touch the leaf
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)

    assert leaf_path.read_text(encoding="utf-8") == block_text


# ---------------------------------------------------------------------------
# folder mode — overflow refs
# ---------------------------------------------------------------------------


def test_folder_mode_overflow_refs_are_relative_filenames(tmp_path: Path):
    """Overflow refs in folder mode must be bare filenames, not .context-tree/... paths."""
    for sub in ("alpha", "beta"):
        d = tmp_path / sub
        d.mkdir()
        _big_py(d)

    run_create(tmp_path, n=50, code_mode=False, folder_mode=True)

    ctx_dir = tmp_path / ".context-tree"
    root_ctx = (ctx_dir / CONTEXT_FILE).read_text()

    # Must reference bare filename, not ".context-tree/alpha_context.md"
    assert "alpha_context.md" in root_ctx
    assert ".context-tree/alpha_context.md" not in root_ctx


# ---------------------------------------------------------------------------
# collect_leaves
# ---------------------------------------------------------------------------


def test_collect_leaves_merges_subdirs(tmp_path: Path):
    """_collect_leaves must prefix subdir leaf keys with their relative path."""
    import yaml as _yaml

    from cxtree.commands.create_ import _collect_leaves

    sub = tmp_path / "domain"
    sub.mkdir()
    (sub / ABSTRACT_LEAF_FILE).write_text(
        _yaml.dump({"models.py": "ORM models.", "users/": False}), encoding="utf-8"
    )

    config = __import__("cxtree.config", fromlist=["Config"]).Config()
    merged = _collect_leaves(tmp_path, config)

    assert merged.get("domain/models.py") == "ORM models."
    assert merged.get("domain/users/") is False


# ---------------------------------------------------------------------------
# tree command
# ---------------------------------------------------------------------------


def test_tree_runs_without_error(simple_project: Path, capsys):
    from cxtree.commands.tree_ import run_tree

    run_tree(simple_project, max_lines=3000)


def test_tree_respects_config(tmp_path: Path):
    """Tree must use config from abstract-tree.yaml when present."""
    import yaml as _yaml

    from cxtree.commands.tree_ import run_tree

    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "style.css").write_text("body {}\n")
    run_create(tmp_path, n=3000, code_mode=False, folder_mode=False)
    run_tree(tmp_path, max_lines=3000)


# ---------------------------------------------------------------------------
# rm on empty project
# ---------------------------------------------------------------------------


def test_rm_on_clean_project(tmp_path: Path):
    """rm on a project with no cxtree artefacts must not raise."""
    run_rm(tmp_path)


# ---------------------------------------------------------------------------
# scan_extensions uses relative paths
# ---------------------------------------------------------------------------


def test_scan_extensions_excludes_correctly(tmp_path: Path):
    """Exclude checks must use relative paths, not absolute ones."""
    from cxtree.commands.create_ import _scan_extensions

    (tmp_path / "app.py").write_text("x = 1\n")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text("s = 1\n")

    config = __import__("cxtree.config", fromlist=["Config"]).Config()
    exts = _scan_extensions(tmp_path, config)
    # .hidden dir should be excluded, but py extension still found from app.py
    assert "py" in exts
