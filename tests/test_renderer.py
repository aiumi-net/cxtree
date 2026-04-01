from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cxtree.renderer import (count_lines, render_code, render_complete,
                             render_context)
from cxtree.walker import FileEntry


def _py(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# render_complete
# ---------------------------------------------------------------------------


def test_render_complete_verbatim(tmp_path: Path):
    p = _py(tmp_path, "f.py", "x = 1\n")
    assert render_complete(p) == "x = 1\n"


def test_render_complete_missing_file(tmp_path: Path):
    assert render_complete(tmp_path / "nonexistent.py") == ""


# ---------------------------------------------------------------------------
# render_code — docstring stripping
# ---------------------------------------------------------------------------


def test_render_code_strips_module_docstring(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        '''Module doc.'''
        x = 1
    """,
    )
    result = render_code(p)
    assert "Module doc" not in result
    assert "x = 1" in result


def test_render_code_strips_function_docstring(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            '''Foo does something.'''
            return 42
    """,
    )
    result = render_code(p)
    assert "Foo does something" not in result
    assert "return 42" in result


def test_render_code_strips_async_function_docstring(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        async def fetch():
            '''Fetch data.'''
            return await db.get()
    """,
    )
    result = render_code(p)
    assert "Fetch data" not in result
    assert "return await" in result


def test_render_code_strips_class_docstring(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        class MyClass:
            '''Class doc.'''
            pass
    """,
    )
    result = render_code(p)
    assert "Class doc" not in result


def test_render_code_strips_method_docstring(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        class MyClass:
            def method(self):
                '''Method doc.'''
                return 1
    """,
    )
    result = render_code(p)
    assert "Method doc" not in result
    assert "return 1" in result


def test_render_code_multiline_docstring_fully_removed(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            '''
            Line one.
            Line two.
            Line three.
            '''
            return 0
    """,
    )
    result = render_code(p)
    assert "Line one" not in result
    assert "Line two" not in result
    assert "return 0" in result


def test_render_code_keeps_marked_docstring(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            '''Keep this.
            # cxtree
            '''
            return 1
    """,
    )
    result = render_code(p)
    assert "Keep this" in result


def test_render_code_keeps_marked_docstring_hashcxtree_nospace(tmp_path: Path):
    """#cxtree without space should also trigger preservation."""
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            '''Keep this.
            #cxtree
            '''
            return 1
    """,
    )
    result = render_code(p)
    assert "Keep this" in result


def test_render_code_syntax_error_returns_file_verbatim(tmp_path: Path):
    p = tmp_path / "bad.py"
    p.write_text("def (broken:\n", encoding="utf-8")
    result = render_code(p)
    assert "def (broken:" in result


def test_render_code_non_py_file_not_docstring_stripped(tmp_path: Path):
    p = tmp_path / "style.css"
    p.write_text("/* comment */\nbody { margin: 0; }\n", encoding="utf-8")
    result = render_code(p)
    assert "/* comment */" in result
    assert "body" in result


# ---------------------------------------------------------------------------
# render_code — CX markers
# ---------------------------------------------------------------------------


def test_cx_plain_removes_line_and_inserts_placeholder(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        x = 1
        SECRET = "abc"  # CX
        y = 2
    """,
    )
    result = render_code(p)
    assert "SECRET" not in result
    assert "# ..." in result
    assert "x = 1" in result
    assert "y = 2" in result


def test_cx_plain_preserves_indentation(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            secret = "x"  # CX
            return 1
    """,
    )
    result = render_code(p)
    assert "secret" not in result
    assert "    # ..." in result  # indented placeholder
    assert "return 1" in result


def test_cx_skip_n_lines(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        x = 1
        # cxtree -2
        hidden1 = True
        hidden2 = True
        visible = True
    """,
    )
    result = render_code(p)
    assert "hidden1" not in result
    assert "hidden2" not in result
    assert "visible" in result
    assert "# ..." in result


def test_cx_skip_n_indented_placeholder(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            # CX -1
            secret = "x"
            return 1
    """,
    )
    result = render_code(p)
    assert "secret" not in result
    assert "    # ..." in result
    assert "return 1" in result


def test_cxtree_marker_variant(tmp_path: Path):
    p = _py(
        tmp_path,
        "f.py",
        """\
        a = 1
        b = 2  # cxtree
        c = 3
    """,
    )
    result = render_code(p)
    assert "b = 2" not in result
    assert "a = 1" in result
    assert "c = 3" in result


def test_cx_marker_inside_kept_docstring_not_processed(tmp_path: Path):
    """'# cxtree' inside a kept docstring must not be treated as a CX directive."""
    p = _py(
        tmp_path,
        "f.py",
        """\
        def foo():
            '''
            # cxtree  ← this line is literal text, not a directive
            Example usage.
            '''
            x = 1
            return x
    """,
    )
    result = render_code(p)
    # Docstring kept (has marker), and the marker line inside it is kept too
    assert "Example usage" in result
    # The marker text itself remains as literal docstring content
    assert "# cxtree" in result
    # Code below docstring is unaffected
    assert "x = 1" in result


def test_cx_marker_on_non_py_file(tmp_path: Path):
    """CX markers work on non-Python files (no docstring handling)."""
    p = tmp_path / "config.sh"
    p.write_text("export A=1\nexport SECRET=x  # CX\nexport B=2\n", encoding="utf-8")
    result = render_code(p)
    assert "SECRET" not in result
    assert "export A=1" in result
    assert "export B=2" in result
    assert "# ..." in result


# ---------------------------------------------------------------------------
# render_context
# ---------------------------------------------------------------------------


def test_render_context_includes_tree(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    files = [FileEntry(tmp_path / "a.py", "a.py")]
    out = render_context(files, code_mode=False)
    assert "a.py" in out
    assert "```" in out


def test_render_context_title_in_file_headers(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    files = [FileEntry(tmp_path / "a.py", "a.py")]
    out = render_context(files, code_mode=False, title="myproject")
    assert "myproject / a.py" in out


def test_render_context_uses_leaf_summary(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    files = [FileEntry(tmp_path / "a.py", "a.py")]
    leaf = {"a.py": "This file contains config."}
    out = render_context(files, code_mode=False, leaf=leaf)
    assert "This file contains config." in out
    assert "x = 1" not in out


def test_render_context_false_leaf_shows_content(tmp_path: Path):
    """A False leaf value must NOT suppress the file content."""
    (tmp_path / "a.py").write_text("x = 1\n")
    files = [FileEntry(tmp_path / "a.py", "a.py")]
    leaf = {"a.py": False}
    out = render_context(files, code_mode=False, leaf=leaf)
    assert "x = 1" in out


def test_render_context_subdir_summary(tmp_path: Path):
    sub = tmp_path / "api"
    sub.mkdir()
    (sub / "routes.py").write_text("x = 1\n")
    files = [FileEntry(sub / "routes.py", "api/routes.py")]
    leaf = {"api/": "All API routes."}
    out = render_context(files, code_mode=False, leaf=leaf)
    assert "All API routes." in out
    assert "x = 1" not in out


def test_render_context_dirs_before_files(tmp_path: Path):
    """Subdirectories must appear before immediate files (VS Code order)."""
    (tmp_path / "z.py").write_text("z = 1\n")
    sub = tmp_path / "alpha"
    sub.mkdir()
    (sub / "a.py").write_text("a = 1\n")
    files = [
        FileEntry(sub / "a.py", "alpha/a.py"),
        FileEntry(tmp_path / "z.py", "z.py"),
    ]
    out = render_context(files, code_mode=False)
    assert out.index("alpha") < out.index("z.py")


def test_render_context_sub_subdir_summary(tmp_path: Path):
    """Summary for a nested subdir (e.g. domain/users/) must be picked up."""
    users = tmp_path / "domain" / "users"
    users.mkdir(parents=True)
    (users / "auth.py").write_text("x = 1\n")
    files = [FileEntry(users / "auth.py", "domain/users/auth.py")]
    # Merged leaf has the prefixed key as built by _collect_leaves
    leaf = {"domain/users/": "Handles user auth."}
    out = render_context(files, code_mode=False, leaf=leaf)
    assert "Handles user auth." in out
    assert "x = 1" not in out


def test_render_context_sub_subdir_false_shows_files(tmp_path: Path):
    users = tmp_path / "domain" / "users"
    users.mkdir(parents=True)
    (users / "auth.py").write_text("x = 1\n")
    files = [FileEntry(users / "auth.py", "domain/users/auth.py")]
    leaf = {"domain/users/": False}
    out = render_context(files, code_mode=False, leaf=leaf)
    assert "x = 1" in out


def test_render_context_file_summary_by_basename(tmp_path: Path):
    """Summary looked up by bare filename must also work."""
    (tmp_path / "utils.py").write_text("x = 1\n")
    files = [FileEntry(tmp_path / "utils.py", "utils.py")]
    leaf = {"utils.py": "Utility helpers."}
    out = render_context(files, code_mode=False, leaf=leaf)
    assert "Utility helpers." in out
    assert "x = 1" not in out


def test_render_context_false_leaf_does_not_bleed_to_subdir_same_name(tmp_path: Path):
    """A False leaf for a subdir file must NOT pick up a root-level summary with the same basename."""
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "models.py").write_text("x = 1\n")
    files = [FileEntry(sub / "models.py", "pkg/models.py")]
    # Root has a summary for models.py, but pkg/models.py is explicitly False
    leaf = {"models.py": "Root models.", "pkg/models.py": False}
    out = render_context(files, code_mode=False, leaf=leaf)
    # The subdir file must show its content, not the root summary
    assert "x = 1" in out
    assert "Root models." not in out


# ---------------------------------------------------------------------------
# count_lines
# ---------------------------------------------------------------------------


def test_count_lines():
    assert count_lines("a\nb\nc\n") == 3
    assert count_lines("a\nb\nc") == 3
    assert count_lines("") == 0


def test_count_lines_single_no_newline():
    assert count_lines("hello") == 1


def test_count_lines_single_with_newline():
    assert count_lines("hello\n") == 1
