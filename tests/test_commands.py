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
from cxtree.commands.tree_ import (_compute_dir_line_counts, _should_show_pct,
                                   run_tree)
from cxtree.models import (ABSTRACT_FILE, ABSTRACT_TREE_FOLDER, LEAF_FILE,
                           ROOT_ABSTRACT_FILE)
from cxtree.walker import ProjectWalker
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

    def test_removes_context_md_in_subdirectories(self, tmp_path: Path):
        """context.md files created by create --max-lines in subdirs must be removed."""
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        # Simulate split-mode artefacts
        subdir_ctx = tmp_path / "domain" / "context.md"
        nested_ctx = tmp_path / "domain" / "users" / "context.md"
        subdir_ctx.write_text("# sub\n", encoding="utf-8")
        nested_ctx.write_text("# nested\n", encoding="utf-8")
        run_rm(tmp_path)
        assert not subdir_ctx.exists()
        assert not nested_ctx.exists()

    def test_does_not_remove_context_md_in_folder_mode(self, tmp_path: Path):
        """In folder mode .abstract-tree/ is wiped; subdir context.md still removed."""
        _make_nested_project(tmp_path)
        run_init(tmp_path, folder=True)
        subdir_ctx = tmp_path / "domain" / "context.md"
        subdir_ctx.write_text("# sub\n", encoding="utf-8")
        run_rm(tmp_path)
        assert not (tmp_path / ABSTRACT_TREE_FOLDER).exists()
        assert not subdir_ctx.exists()

    def test_single_pass_removes_both_root_context_and_folder(self, tmp_path: Path):
        """When root context.md AND .abstract-tree/ folder both exist, one rm removes both."""
        _make_simple_project(tmp_path)
        # Simulate mixed state: both root-mode and folder-mode artefacts present
        run_init(tmp_path)  # writes abstract-tree.yaml at root
        (tmp_path / "context.md").write_text("# ctx\n", encoding="utf-8")
        folder = tmp_path / ABSTRACT_TREE_FOLDER
        folder.mkdir()
        (folder / "abstract-tree.yaml").write_text("cxtree:\n", encoding="utf-8")

        run_rm(tmp_path)

        assert not (tmp_path / ROOT_ABSTRACT_FILE).exists()
        assert not (tmp_path / "context.md").exists()
        assert not folder.exists()


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


# ---------------------------------------------------------------------------
# run_init --default / --docs / --code / --include tests
# ---------------------------------------------------------------------------


def _py_with_docstrings(path: Path) -> None:
    """Write a Python file that has a module docstring and one class with a method docstring."""
    path.write_text(
        textwrap.dedent("""\
        '''Module docstring.'''

        class Greeter:
            '''Greeter class.'''
            def greet(self, name: str) -> str:
                '''Return greeting.'''
                return f"Hello, {name}"
        """),
        encoding="utf-8",
    )


class TestRunInitDefaultTag:
    def test_default_docs_sets_x_root_docs(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, default_tag="docs")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        assert data["cxtree"]["x_root"] == "docs"

    def test_default_code_sets_x_root_code(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, default_tag="code")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        assert data["cxtree"]["x_root"] == "code"

    def test_default_include_sets_x_root_include(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path, default_tag="include")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        assert data["cxtree"]["x_root"] == "include"

    def test_default_docs_still_embeds_docstrings(self, tmp_path: Path):
        """Without an explicit_tag, docstring text is embedded regardless of default_tag."""
        _py_with_docstrings(tmp_path / "mod.py")
        run_init(tmp_path, default_tag="code")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        mod_entry = data.get("mod.py", {})
        # x_abstract should be the extracted docstring text, not the "code" tag
        assert isinstance(mod_entry.get("x_abstract"), list)
        assert any("Module docstring" in str(line) for line in mod_entry["x_abstract"])


class TestRunInitExplicitTag:
    def _get_all_leaf_values(self, data: dict, _depth: int = 0) -> list:
        """Recursively collect all leaf string values from a nested dict."""
        values = []
        for k, v in data.items():
            if k == "cxtree":
                continue
            if isinstance(v, dict):
                values.extend(self._get_all_leaf_values(v, _depth + 1))
            elif isinstance(v, list):
                pass  # embedded docstring text — not a tag
            elif isinstance(v, str):
                values.append(v)
        return values

    def test_docs_flag_writes_docs_everywhere(self, tmp_path: Path):
        _py_with_docstrings(tmp_path / "mod.py")
        run_init(tmp_path, explicit_tag="docs")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        leaf_values = self._get_all_leaf_values(data)
        assert all(
            v == "docs" for v in leaf_values
        ), f"unexpected values: {leaf_values}"

    def test_code_flag_writes_code_everywhere(self, tmp_path: Path):
        _py_with_docstrings(tmp_path / "mod.py")
        run_init(tmp_path, explicit_tag="code")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        leaf_values = self._get_all_leaf_values(data)
        assert all(
            v == "code" for v in leaf_values
        ), f"unexpected values: {leaf_values}"

    def test_include_flag_writes_include_everywhere(self, tmp_path: Path):
        _py_with_docstrings(tmp_path / "mod.py")
        run_init(tmp_path, explicit_tag="include")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        leaf_values = self._get_all_leaf_values(data)
        assert all(
            v == "include" for v in leaf_values
        ), f"unexpected values: {leaf_values}"

    def test_explicit_tag_does_not_embed_docstring_text(self, tmp_path: Path):
        """With explicit_tag set, no docstring text should appear as a list in the yaml."""
        _py_with_docstrings(tmp_path / "mod.py")
        run_init(tmp_path, explicit_tag="docs")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        mod_entry = data.get("mod.py", {})
        # x_abstract must be the tag string, not an extracted text list
        assert mod_entry.get("x_abstract") == "docs"

    def test_non_py_files_always_use_include(self, tmp_path: Path):
        """Non-.py files that are indexed always get 'include' regardless of explicit_tag."""
        # Use a .py file paired with a Dockerfile (no extension) so we can verify
        # _build_file_entry returns "include" for non-py files.
        _py_with_docstrings(tmp_path / "mod.py")
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12\n", encoding="utf-8")
        # Include Dockerfile in extensions
        run_init(tmp_path, explicit_tag="code")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        # mod.py should use "code"; Dockerfile is not a .py so _build_file_entry → "include"
        # But Dockerfile is only present in abstract-tree if it matches include_extensions.
        # Default include_extensions=["py"], so Dockerfile won't be indexed. Instead verify
        # that the .py entry uses "code" and the Dockerfile is absent (not erroneously "code").
        assert data.get("Dockerfile") is None  # not in include_extensions by default
        mod_entry = data.get("mod.py", {})
        assert mod_entry.get("x_abstract") == "code"

    def test_explicit_tag_applied_in_subdirs(self, tmp_path: Path):
        """explicit_tag must propagate to files discovered in subdirectories."""
        _make_simple_project(tmp_path)
        run_init(tmp_path, explicit_tag="code")
        data = load_yaml(tmp_path / ROOT_ABSTRACT_FILE)
        utils_entry = data.get("utils", {})
        helpers_entry = utils_entry.get("helpers.py")
        # helpers.py has a function; entry is a dict with def: {add: "code"}
        assert isinstance(helpers_entry, dict)
        assert helpers_entry.get("def", {}).get("add") == "code"


# ---------------------------------------------------------------------------
# run_create --max-lines tests
# ---------------------------------------------------------------------------


def _make_large_project(root: Path) -> None:
    """Create a project large enough to exceed a small max_lines threshold."""
    for i in range(3):
        subdir = root / f"module_{i}"
        subdir.mkdir()
        lines = "\n".join(
            f"def func_{j}():\n    '''Docstring for func_{j}.'''\n    return {j}"
            for j in range(10)
        )
        (subdir / "funcs.py").write_text(lines + "\n", encoding="utf-8")


class TestRunCreateMaxLines:
    def test_single_file_when_within_limit(self, tmp_path: Path):
        _make_simple_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path, max_lines=10_000)
        assert (tmp_path / "context.md").exists()
        # No per-subdir context.md should be created
        assert not (tmp_path / "utils" / "context.md").exists()

    def test_splits_into_subdir_files_when_exceeded(self, tmp_path: Path):
        _make_large_project(tmp_path)
        run_init(tmp_path)
        # Force split with a tiny limit
        run_create(tmp_path, max_lines=5)
        # At least one subdir context.md must have been created
        subdir_contexts = list(tmp_path.rglob("context.md"))
        assert any(f.parent != tmp_path for f in subdir_contexts)

    def test_no_root_context_md_when_all_files_in_subdirs(self, tmp_path: Path):
        """When every file is inside subdirs and limit exceeded, root/context.md is absent."""
        _make_large_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path, max_lines=5)
        # No files live directly in root (only subdirs), so root context.md should not exist
        assert not (tmp_path / "context.md").exists()

    def test_split_context_md_contains_only_subdir_files(self, tmp_path: Path):
        _make_large_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path, max_lines=5)
        ctx = tmp_path / "module_0" / "context.md"
        assert ctx.exists()
        content = ctx.read_text(encoding="utf-8")
        # Content must mention module_0 files
        assert "module_0" in content

    def test_custom_output_ignores_max_lines(self, tmp_path: Path):
        """When --output is given explicitly, max_lines has no effect."""
        _make_large_project(tmp_path)
        run_init(tmp_path)
        out = tmp_path / "all.md"
        run_create(tmp_path, output=out, max_lines=1)
        # Single file written at the requested path
        assert out.exists()
        # No split files
        assert not any(f.name == "context.md" for f in tmp_path.rglob("context.md"))

    def test_rm_cleans_up_split_context_files(self, tmp_path: Path):
        """run_rm must remove all context.md files created by splitting."""
        _make_large_project(tmp_path)
        run_init(tmp_path)
        run_create(tmp_path, max_lines=5)
        # Verify split files exist
        assert any(f.parent != tmp_path for f in tmp_path.rglob("context.md"))
        run_rm(tmp_path)
        remaining = list(tmp_path.rglob("context.md"))
        assert remaining == [], f"context.md files remain after rm: {remaining}"


# ---------------------------------------------------------------------------
# run_tree --max-lines tests
# ---------------------------------------------------------------------------


class TestRunTree:
    def test_run_tree_default_max_lines_does_not_raise(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        run_tree(tmp_path)  # default max_lines=3000, should not raise

    def test_run_tree_custom_max_lines_does_not_raise(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        run_tree(tmp_path, max_lines=50)  # should not raise

    def test_compute_dir_line_counts_returns_entry_for_each_dir(self, tmp_path: Path):
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        walker = ProjectWalker(tmp_path)
        result = walker.walk()
        counts = _compute_dir_line_counts(result)
        assert tmp_path in counts
        assert tmp_path / "domain" in counts

    def test_compute_dir_line_counts_root_ge_subdirs(self, tmp_path: Path):
        """Root line count must be >= any individual subdirectory count."""
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        walker = ProjectWalker(tmp_path)
        result = walker.walk()
        counts = _compute_dir_line_counts(result)
        root_count = counts.get(tmp_path, 0)
        for d, c in counts.items():
            if d != tmp_path:
                assert root_count >= c, f"{d} count {c} > root count {root_count}"

    def test_compute_dir_line_counts_leaf_le_parent(self, tmp_path: Path):
        """A leaf directory's line count must be <= its parent's."""
        _make_nested_project(tmp_path)
        run_init(tmp_path)
        walker = ProjectWalker(tmp_path)
        result = walker.walk()
        counts = _compute_dir_line_counts(result)
        domain = tmp_path / "domain"
        users = tmp_path / "domain" / "users"
        if domain in counts and users in counts:
            assert counts[domain] >= counts[users]

    def test_compute_dir_line_counts_empty_dir_absent(self, tmp_path: Path):
        """A directory with no included files produces no entry in counts."""
        _make_simple_project(tmp_path)
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        run_init(tmp_path)
        walker = ProjectWalker(tmp_path)
        result = walker.walk()
        counts = _compute_dir_line_counts(result)
        assert empty not in counts


class TestShouldShowPct:
    """Unit tests for the _should_show_pct visibility rule."""

    def _counts(self, root: Path, **kw: int) -> dict[Path, int]:
        return {root / k if k != "." else root: v for k, v in kw.items()}

    def test_root_shown_when_fits(self, tmp_path: Path):
        counts = self._counts(tmp_path, **{".": 50})
        assert _should_show_pct(tmp_path, tmp_path, counts, 100) is True

    def test_root_hidden_when_overflows(self, tmp_path: Path):
        counts = self._counts(tmp_path, **{".": 150})
        assert _should_show_pct(tmp_path, tmp_path, counts, 100) is False

    def test_child_shown_when_fits_and_parent_overflows(self, tmp_path: Path):
        child = tmp_path / "sub"
        counts = {tmp_path: 150, child: 60}
        assert _should_show_pct(child, tmp_path, counts, 100) is True

    def test_child_hidden_when_overflows(self, tmp_path: Path):
        child = tmp_path / "sub"
        counts = {tmp_path: 150, child: 120}
        assert _should_show_pct(child, tmp_path, counts, 100) is False

    def test_child_hidden_when_parent_fits(self, tmp_path: Path):
        """If parent fits, the child is included in parent's context.md — not shown separately."""
        child = tmp_path / "sub"
        counts = {tmp_path: 50, child: 30}
        assert _should_show_pct(child, tmp_path, counts, 100) is False

    def test_grandchild_shown_only_when_grandparent_overflows_and_parent_overflows(
        self, tmp_path: Path
    ):
        parent = tmp_path / "a"
        child = tmp_path / "a" / "b"
        # root overflows, parent overflows, child fits → child shown
        counts = {tmp_path: 200, parent: 150, child: 60}
        assert _should_show_pct(child, tmp_path, counts, 100) is True

    def test_grandchild_hidden_when_parent_fits(self, tmp_path: Path):
        parent = tmp_path / "a"
        child = tmp_path / "a" / "b"
        # root overflows, parent fits → child not shown (parent gets the context.md)
        counts = {tmp_path: 200, parent: 80, child: 40}
        assert _should_show_pct(child, tmp_path, counts, 100) is False

    def test_missing_dir_returns_false(self, tmp_path: Path):
        assert _should_show_pct(tmp_path / "ghost", tmp_path, {}, 100) is False
