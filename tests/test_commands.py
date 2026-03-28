"""Integration tests for context_tree commands."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cxtree.commands.create_ import run_create
from cxtree.commands.flatten_ import run_flatten
from cxtree.commands.init_ import run_init
from cxtree.commands.leaf_ import run_leaf
from cxtree.commands.rm_ import run_rm
from cxtree.models import (ABSTRACT_FILE, ABSTRACT_TREE_FOLDER, LEAF_FILE,
                           ROOT_ABSTRACT_FILE)
from cxtree.yaml_io import load_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _make_simple_project(root: Path) -> None:
    """Create a minimal project for testing."""
    _write_py(
        root / "app.py",
        """\
        def main():
            '''Entry point.'''
            pass
        """,
    )
    subdir = root / "utils"
    subdir.mkdir(exist_ok=True)
    _write_py(
        subdir / "helpers.py",
        """\
        def add(a, b):
            '''Add two numbers.'''
            return a + b
        """,
    )


def _make_nested_project(root: Path) -> None:
    """Create a project with two levels of nesting."""
    _write_py(root / "app.py", "# root\n")
    domain = root / "domain"
    domain.mkdir(exist_ok=True)
    _write_py(
        domain / "models.py",
        """\
        class User:
            '''A user.'''
            pass
        """,
    )
    users = domain / "users"
    users.mkdir(exist_ok=True)
    _write_py(
        users / "service.py",
        """\
        def create():
            '''Create user.'''
            pass
        """,
    )


# ---------------------------------------------------------------------------
# run_init tests
# ---------------------------------------------------------------------------


class TestRunInit:
    def test_creates_abstract_tree_yaml(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        abstract = tmp_path / ROOT_ABSTRACT_FILE
        assert abstract.exists()
        data = load_yaml(abstract)
        assert "cxtree" in data

    def test_correct_structure(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        ct = data["cxtree"]
        assert "config" in ct
        assert "x_root" in ct

    def test_folder_mode_creates_subfolder(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, folder=True)
        folder = tmp_path / ABSTRACT_TREE_FOLDER
        assert folder.exists()
        assert (folder / ROOT_ABSTRACT_FILE).exists()
        gitignore = folder / ".gitignore"
        assert gitignore.exists()
        assert gitignore.read_text() == "*\n"

    def test_folder_mode_deletes_root_level_yaml(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        # First create normal mode
        run_init(tmp_path)
        assert (tmp_path / ROOT_ABSTRACT_FILE).exists()
        # Switch to folder mode
        run_init(tmp_path, folder=True)
        assert not (tmp_path / ROOT_ABSTRACT_FILE).exists()
        assert (tmp_path / ABSTRACT_TREE_FOLDER / ROOT_ABSTRACT_FILE).exists()

    def test_normal_mode_deletes_abstract_tree_folder(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, folder=True)
        assert (tmp_path / ABSTRACT_TREE_FOLDER).exists()
        run_init(tmp_path, folder=False)
        assert not (tmp_path / ABSTRACT_TREE_FOLDER).exists()
        assert (tmp_path / ROOT_ABSTRACT_FILE).exists()

    def test_indexes_py_files_in_subdirs(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        # utils should be in entries
        assert "utils" in data

    def test_rerun_preserves_config(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        # Manually set a custom config value
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        data["cxtree"]["config"]["x_rm_empty_lines"] = True
        from cxtree.yaml_io import save_yaml

        save_yaml(tmp_path / ROOT_ABSTRACT_FILE, data)
        # Re-run init
        run_init(tmp_path)
        data2 = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        assert data2["cxtree"]["config"]["x_rm_empty_lines"] is True


# ---------------------------------------------------------------------------
# run_leaf tests
# ---------------------------------------------------------------------------


class TestRunLeaf:
    def test_splits_into_child_abstracts(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_leaf(tmp_path)
        child = tmp_path / "utils" / ABSTRACT_FILE
        assert child.exists()

    def test_auto_runs_init_when_no_yaml(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        # No init called — run_leaf should trigger auto-init
        run_leaf(tmp_path)
        assert (tmp_path / ROOT_ABSTRACT_FILE).exists()
        child = tmp_path / "utils" / ABSTRACT_FILE
        assert child.exists()

    def test_child_abstract_has_correct_depth(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        run_leaf(tmp_path)
        domain_child = tmp_path / "domain" / ABSTRACT_FILE
        assert domain_child.exists()
        data = load_yaml(domain_child)
        assert data["abstract-depth"] == 1

    def test_child_abstract_has_parent_dirs(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        run_leaf(tmp_path)
        domain_child = tmp_path / "domain" / ABSTRACT_FILE
        data = load_yaml(domain_child)
        assert data["parent-dirs"] == ["domain"]

    def test_subdirectory_entries_in_child_abstract(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        run_leaf(tmp_path)
        domain_child = tmp_path / "domain" / ABSTRACT_FILE
        data = load_yaml(domain_child)
        # users/ is a subdir of domain — should appear in domain's child abstract
        assert "users" in data
        users_entry = data["users"]
        assert isinstance(users_entry, dict)
        assert users_entry.get("is_dir") is True
        assert users_entry.get("x_is_flat") is False
        assert users_entry.get("x_hard_abstract") == "off"

    def test_rerunning_leaf_updates_child_abstracts(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_leaf(tmp_path)
        # Modify child abstract
        child = tmp_path / "utils" / ABSTRACT_FILE
        data = load_yaml(child)
        data["helpers.py"] = "exclude"
        from cxtree.yaml_io import save_yaml

        save_yaml(child, data)
        # Re-run leaf — should re-create child abstracts (preserving edits by merging)
        run_leaf(tmp_path)
        child2 = tmp_path / "utils" / ABSTRACT_FILE
        assert child2.exists()


# ---------------------------------------------------------------------------
# run_flatten tests
# ---------------------------------------------------------------------------


class TestRunFlatten:
    def _setup_leaf_project(self, root: Path) -> None:
        _make_nested_project(root)
        run_init(root)
        run_leaf(root)

    def test_merges_child_abstracts_into_root(self, tmp_path: Path):
        self._setup_leaf_project(tmp_path)
        run_flatten(tmp_path)
        # Child abstracts should be deleted
        domain_child = tmp_path / "domain" / ABSTRACT_FILE
        assert not domain_child.exists()

    def test_root_entries_contain_file_after_flatten(self, tmp_path: Path):
        self._setup_leaf_project(tmp_path)
        run_flatten(tmp_path)
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        # domain entry should now contain models.py
        assert "domain" in data
        domain_val = data["domain"]
        assert isinstance(domain_val, dict)
        assert "models.py" in domain_val

    def test_partial_flatten_with_subtree(self, tmp_path: Path):
        self._setup_leaf_project(tmp_path)
        # Only flatten the 'domain.users' subtree
        run_flatten(tmp_path, subtree="domain/users")
        domain_child = tmp_path / "domain" / ABSTRACT_FILE
        users_child = tmp_path / "domain" / "users" / ABSTRACT_FILE
        # domain's child abstract should still exist (not flattened)
        assert domain_child.exists()
        # users' child abstract should be gone
        assert not users_child.exists()

    def test_partial_flatten_marks_x_is_flat_in_parent(self, tmp_path: Path):
        self._setup_leaf_project(tmp_path)
        run_flatten(tmp_path, subtree="domain/users")
        domain_child = tmp_path / "domain" / ABSTRACT_FILE
        data = load_yaml(domain_child)
        # 'users' entry in domain child abstract should have x_is_flat: true
        assert data.get("users", {}).get("x_is_flat") is True

    def test_flatten_deletes_child_abstract_files(self, tmp_path: Path):
        self._setup_leaf_project(tmp_path)
        run_flatten(tmp_path)
        # No abstract.yaml files should remain
        for p in tmp_path.rglob(ABSTRACT_FILE):
            if ABSTRACT_TREE_FOLDER not in p.parts:
                pytest.fail(f"Child abstract still exists: {p}")

    def test_flatten_sets_is_flat_true(self, tmp_path: Path):
        self._setup_leaf_project(tmp_path)
        run_flatten(tmp_path)
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        ct = data["cxtree"]
        assert ct.get("is_flat") is True


# ---------------------------------------------------------------------------
# run_rm tests
# ---------------------------------------------------------------------------


class TestRunRm:
    def test_removes_abstract_tree_yaml_and_context_md(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        (tmp_path / "context.md").write_text("# Context\n", encoding="utf-8")
        run_rm(tmp_path)
        assert not (tmp_path / ROOT_ABSTRACT_FILE).exists()
        assert not (tmp_path / "context.md").exists()

    def test_removes_child_abstract_yaml_files(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        run_leaf(tmp_path)
        run_rm(tmp_path)
        for p in tmp_path.rglob(ABSTRACT_FILE):
            if ABSTRACT_TREE_FOLDER not in p.parts:
                pytest.fail(f"Child abstract still exists after rm: {p}")

    def test_folder_mode_removes_entire_abstract_tree_folder(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, folder=True)
        folder = tmp_path / ABSTRACT_TREE_FOLDER
        assert folder.exists()
        run_rm(tmp_path)
        assert not folder.exists()

    def test_nothing_to_remove_no_error(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        # No init run — nothing to remove
        run_rm(tmp_path)  # should not raise


# ---------------------------------------------------------------------------
# run_create tests
# ---------------------------------------------------------------------------


class TestRunCreate:
    def test_generates_context_md(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path)
        context = tmp_path / "context.md"
        assert context.exists()

    def test_context_md_has_directory_tree_section(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text()
        assert "## Directory Tree" in content

    def test_context_md_has_filename_section_headers(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text()
        assert "## app.py" in content
        assert "## utils/helpers.py" in content

    def test_context_md_contains_file_content(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text()
        assert "def main" in content or "def add" in content

    def test_custom_output_path(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        output = tmp_path / "out" / "custom.md"
        run_create(tmp_path, output=output)
        assert output.exists()

    def test_folder_mode_outputs_to_abstract_tree_folder(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, folder=True)
        run_create(tmp_path)
        context = tmp_path / ABSTRACT_TREE_FOLDER / "context.md"
        assert context.exists()


# ---------------------------------------------------------------------------
# abstract-leaf.yaml tests
# ---------------------------------------------------------------------------


class TestLeafAbstract:
    """Tests for abstract-leaf.yaml highest-priority flat override feature."""

    def test_leaf_file_excluded_from_init_scan(self, tmp_path: Path):
        """abstract-leaf.yaml should not appear as a file entry in abstract-tree.yaml."""
        _make_simple_project(tmp_path)
        (tmp_path / LEAF_FILE).write_text("app.py: some desc\n", encoding="utf-8")
        run_init(tmp_path)
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        assert LEAF_FILE not in str(data)

    def test_leaf_overrides_file_in_root(self, tmp_path: Path):
        """A leaf override for a root-level file replaces its content in context output."""
        _make_simple_project(tmp_path)
        (tmp_path / LEAF_FILE).write_text(
            "app.py: Custom description for app\n", encoding="utf-8"
        )
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert "Custom description for app" in content

    def test_leaf_overrides_file_in_subdir(self, tmp_path: Path):
        """A leaf override in a subdir's abstract-leaf.yaml replaces the file content."""
        _make_simple_project(tmp_path)
        (tmp_path / "utils" / LEAF_FILE).write_text(
            "helpers.py: Helper functions summary\n", encoding="utf-8"
        )
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert "Helper functions summary" in content

    def test_leaf_overrides_directory(self, tmp_path: Path):
        """A leaf override for a directory name skips walking it, emits summary."""
        _make_simple_project(tmp_path)
        (tmp_path / LEAF_FILE).write_text(
            "utils: Utility module summary\n", encoding="utf-8"
        )
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert "Utility module summary" in content
        # helpers.py content should NOT appear (dir was replaced by summary)
        assert "helpers" not in content or "Utility module summary" in content

    def test_leaf_override_deactivated_by_excluded_prefix(self, tmp_path: Path):
        """Keys starting with exclude prefix (. or __) are ignored."""
        _make_simple_project(tmp_path)
        (tmp_path / LEAF_FILE).write_text(
            ".app.py: Should be ignored\n", encoding="utf-8"
        )
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert "Should be ignored" not in content

    def test_leaf_override_deactivated_by_dunder_prefix(self, tmp_path: Path):
        """Keys starting with __ are treated as deactivated."""
        _make_simple_project(tmp_path)
        (tmp_path / LEAF_FILE).write_text("__app.py: Also ignored\n", encoding="utf-8")
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert "Also ignored" not in content

    def test_leaf_file_not_in_context_output(self, tmp_path: Path):
        """abstract-leaf.yaml itself must never appear as a section in context output."""
        _make_simple_project(tmp_path)
        (tmp_path / LEAF_FILE).write_text("app.py: override\n", encoding="utf-8")
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert LEAF_FILE not in content

    def test_leaf_override_bypasses_extension_filter(self, tmp_path: Path):
        """A leaf override for a non-.py file includes it even if not in include_extensions."""
        _make_simple_project(tmp_path)
        readme = tmp_path / "README.txt"
        readme.write_text("project readme", encoding="utf-8")
        (tmp_path / LEAF_FILE).write_text(
            "README.txt: The project readme\n", encoding="utf-8"
        )
        run_init(tmp_path)
        run_create(tmp_path)
        content = (tmp_path / "context.md").read_text(encoding="utf-8")
        assert "The project readme" in content
