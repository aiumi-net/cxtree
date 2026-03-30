"""Tests for context_tree/source.py"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from cxtree.source import (_apply_minus_tags, _parse_inline_tag, render_class,
                           render_function, render_python_file)

# ---------------------------------------------------------------------------
# _parse_inline_tag
# ---------------------------------------------------------------------------


class TestParseInlineTag:
    def test_plus_two(self):
        assert _parse_inline_tag("    x = 1  # ++") == ("++", 2)

    def test_plus_three(self):
        assert _parse_inline_tag("some code  # +++") == ("++", 3)

    def test_minus_two(self):
        assert _parse_inline_tag("    y = 2  # --") == ("--", 2)

    def test_minus_three(self):
        assert _parse_inline_tag("z = 3  # ---") == ("--", 3)

    def test_single_dash_no_match(self):
        # Single dash is not a valid tag
        assert _parse_inline_tag("x = 1  # -") is None

    def test_regular_comment(self):
        assert _parse_inline_tag("x = 1  # this is a comment") is None

    def test_no_tag(self):
        assert _parse_inline_tag("x = 1") is None

    def test_empty_line(self):
        assert _parse_inline_tag("") is None

    def test_plus_with_spaces(self):
        assert _parse_inline_tag("x  #  ++") == ("++", 2)

    def test_minus_with_spaces(self):
        assert _parse_inline_tag("x  #  ---") == ("--", 3)


# ---------------------------------------------------------------------------
# _apply_minus_tags
# ---------------------------------------------------------------------------


class TestApplyMinusTags:
    def test_basic(self):
        lines = [
            "    x = 1  # --\n",
            "    y = 2\n",
            "    z = 3\n",
        ]
        result = _apply_minus_tags(lines)
        # -- means: replace this line + next 1 line with placeholder
        assert result == ["    # --\n", "    z = 3\n"]

    def test_multi_line_removal(self):
        lines = [
            "    a = 1  # ---\n",
            "    b = 2\n",
            "    c = 3\n",
            "    d = 4\n",
        ]
        result = _apply_minus_tags(lines)
        # --- means: replace this line + next 2 lines (3 total) with placeholder
        assert result == ["    # ---\n", "    d = 4\n"]

    def test_multiple_tags(self):
        lines = [
            "    a = 1  # --\n",
            "    b = 2\n",
            "    c = 3  # --\n",
            "    d = 4\n",
        ]
        result = _apply_minus_tags(lines)
        assert result == ["    # --\n", "    # --\n"]

    def test_tag_at_end(self):
        lines = [
            "    x = 1\n",
            "    y = 2  # --\n",
            "    z = 3\n",
        ]
        result = _apply_minus_tags(lines)
        assert result == ["    x = 1\n", "    # --\n"]

    def test_no_tags(self):
        lines = ["    x = 1\n", "    y = 2\n"]
        assert _apply_minus_tags(lines) == lines


# ---------------------------------------------------------------------------
# render_function
# ---------------------------------------------------------------------------


def _parse_func(src: str, name: str = "foo") -> tuple[ast.FunctionDef, list[str]]:
    tree = ast.parse(src)
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node, src.splitlines(keepends=True)  # type: ignore
    raise ValueError(f"Function {name!r} not found")


class TestRenderFunction:
    def test_docs_with_docstring(self):
        src = textwrap.dedent("""\
        def foo():
            '''This is the docstring.'''
            x = 1
        """)
        node, lines = _parse_func(src)
        result = render_function(node, lines, "docs")
        assert result is not None
        rendered = "".join(result)
        assert "def foo():" in rendered
        assert "This is the docstring." in rendered
        assert "# ..." in rendered
        # Should NOT show x = 1
        assert "x = 1" not in rendered

    def test_docs_with_docstring_and_plus_tag(self):
        src = textwrap.dedent("""\
        def foo():
            '''Docstring here.'''
            x = 1  # ++
            y = 2
        """)
        node, lines = _parse_func(src)
        result = render_function(node, lines, "docs")
        assert result is not None
        rendered = "".join(result)
        assert "def foo():" in rendered
        assert "Docstring here." in rendered
        # The ++ line should be shown
        assert "x = 1" in rendered
        # When the ++ window covers to the end of the body, no trailing # ...
        # x = 1 is line 1 of body, N=2 means show 2 lines (x=1, y=2)
        # all_covered = (0 + 2) >= 2 = True, so no trailing # ...
        assert "# ..." not in rendered

    def test_docs_with_no_docstring_and_minus_tag(self):
        src = textwrap.dedent("""\
        def foo():
            x = 1  # ---
            y = 2
            z = 3
            w = 4
        """)
        node, lines = _parse_func(src)
        result = render_function(node, lines, "docs")
        assert result is not None
        rendered = "".join(result)
        assert "def foo():" in rendered
        # --- removes itself + 2 more lines (y and z), leaving w
        assert "w = 4" in rendered
        assert "y = 2" not in rendered
        assert "z = 3" not in rendered

    def test_code_tag_no_docstring(self):
        src = textwrap.dedent("""\
        def bar():
            '''My docstring.'''
            return 42
        """)
        node, lines = _parse_func(src, "bar")
        result = render_function(node, lines, "code")
        assert result is not None
        rendered = "".join(result)
        assert "def bar():" in rendered
        assert "return 42" in rendered
        # Docstring should be stripped
        assert "My docstring." not in rendered

    def test_exclude_tag_returns_none(self):
        src = "def foo():\n    pass\n"
        node, lines = _parse_func(src)
        result = render_function(node, lines, "exclude")
        assert result is None

    def test_include_tag(self):
        src = textwrap.dedent("""\
        def baz():
            '''Docstring.'''
            return 1
        """)
        node, lines = _parse_func(src, "baz")
        result = render_function(node, lines, "include")
        assert result is not None
        rendered = "".join(result)
        assert "def baz():" in rendered
        assert "Docstring." in rendered
        assert "return 1" in rendered


# ---------------------------------------------------------------------------
# render_class
# ---------------------------------------------------------------------------


def _parse_class(src: str, name: str = "MyClass") -> tuple[ast.ClassDef, list[str]]:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node, src.splitlines(keepends=True)
    raise ValueError(f"Class {name!r} not found")


class TestRenderClass:
    def test_exclude_returns_none(self):
        src = "class Foo:\n    pass\n"
        node, lines = _parse_class(src, "Foo")
        result = render_class(node, lines, "exclude", {})
        assert result is None

    def test_docs_with_docstring(self):
        src = textwrap.dedent("""\
        class MyClass:
            '''Class docstring.'''
            def method(self):
                '''Method docstring.'''
                pass
        """)
        node, lines = _parse_class(src)
        result = render_class(node, lines, "docs", {})
        assert result is not None
        rendered = "".join(result)
        assert "class MyClass:" in rendered
        assert "Class docstring." in rendered
        assert "def method" in rendered

    def test_method_with_exclude_config(self):
        src = textwrap.dedent("""\
        class MyClass:
            def public(self):
                pass
            def _private(self):
                pass
        """)
        node, lines = _parse_class(src)
        method_configs = {"_private": ("exclude", None, None)}
        result = render_class(node, lines, "include", method_configs)
        assert result is not None
        rendered = "".join(result)
        assert "def public" in rendered
        assert "_private" not in rendered

    def test_method_with_docs_override(self):
        src = textwrap.dedent("""\
        class MyClass:
            def do_thing(self):
                '''Do something.'''
                x = 1
                return x
        """)
        node, lines = _parse_class(src)
        method_configs = {"do_thing": ("docs", None, None)}
        result = render_class(node, lines, "include", method_configs)
        assert result is not None
        rendered = "".join(result)
        assert "def do_thing" in rendered
        assert "Do something." in rendered
        assert "# ..." in rendered
        assert "x = 1" not in rendered

    def test_no_spurious_placeholder_without_docstring(self):
        """Class with no docstring but class-level attributes must NOT get # ... placeholder."""
        src = textwrap.dedent("""\
        class AuthService:
            _FAKE = "secret"

            def login(self):
                return True
        """)
        node, lines = _parse_class(src, "AuthService")
        result = render_class(node, lines, "docs", {}, rm_empty_lines_docs=True)
        assert result is not None
        rendered = "".join(result)
        # No docstring → full body should be shown; no stray # ... before the method
        assert "class AuthService:" in rendered
        assert "def login" in rendered
        assert rendered.count("# ...") == 0

    def test_placeholder_present_when_docstring_exists(self):
        """Class WITH a docstring and class-level attributes should still get # ... placeholder."""
        src = textwrap.dedent("""\
        class Service:
            '''Service docstring.'''
            _SECRET = "x"

            def run(self):
                return True
        """)
        node, lines = _parse_class(src, "Service")
        result = render_class(node, lines, "docs", {}, rm_empty_lines_docs=True)
        assert result is not None
        rendered = "".join(result)
        assert "Service docstring." in rendered
        assert "# ..." in rendered


# ---------------------------------------------------------------------------
# render_python_file (end-to-end)
# ---------------------------------------------------------------------------


class TestRenderPythonFile:
    def test_include_tag_full_output(self, tmp_path: Path):
        src = "def foo():\n    return 1\n"
        f = tmp_path / "mod.py"
        f.write_text(src)
        result = render_python_file(f, None, "include")
        assert "def foo():" in result
        assert "return 1" in result

    def test_exclude_tag_empty(self, tmp_path: Path):
        src = "def foo():\n    return 1\n"
        f = tmp_path / "mod.py"
        f.write_text(src)
        result = render_python_file(f, None, "exclude")
        assert result == ""

    def test_docs_tag_shows_docstrings(self, tmp_path: Path):
        src = textwrap.dedent("""\
        def greet(name):
            '''Greet someone.'''
            print(f"Hello, {name}")
        """)
        f = tmp_path / "mod.py"
        f.write_text(src)
        result = render_python_file(f, None, "docs")
        assert "def greet" in result
        assert "Greet someone." in result
        assert "# ..." in result

    def test_file_cfg_with_symbol_config(self, tmp_path: Path):
        src = textwrap.dedent("""\
        def visible():
            '''Visible func.'''
            pass

        def hidden():
            '''Hidden func.'''
            pass
        """)
        f = tmp_path / "mod.py"
        f.write_text(src)
        file_cfg = {"def": {"hidden": "exclude"}}
        result = render_python_file(f, file_cfg, "docs")
        assert "visible" in result
        assert "hidden" not in result

    def test_syntax_error_returns_raw(self, tmp_path: Path):
        src = "def foo(:\n    pass\n"
        f = tmp_path / "broken.py"
        f.write_text(src)
        result = render_python_file(f, None, "docs")
        # Falls back to raw source
        assert "def foo(:" in result
