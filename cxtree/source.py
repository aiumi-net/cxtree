from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .models import DEFAULT_TAG, VALID_TAGS, parse_entry_value

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_lines(node: ast.AST, src_lines: list[str]) -> list[str]:
    """Return the source lines for an AST node (1-indexed end_lineno)."""
    start = node.lineno - 1  # type: ignore[attr-defined]
    end = node.end_lineno  # type: ignore[attr-defined]
    return src_lines[start:end]


def _get_docstring_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> ast.Constant | None:
    """Return the docstring AST Constant node if present, else None."""
    if not node.body:
        return None
    first = node.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.value
    return None


def _docstring_line_range(node: ast.AST) -> tuple[int, int] | None:
    """Return (start_lineno, end_lineno) 1-indexed of the docstring, or None."""
    ds = _get_docstring_node(node)  # type: ignore[arg-type]
    if ds is None:
        return None
    return ds.lineno, ds.end_lineno  # type: ignore[attr-defined]


def _strip_docstring_from_lines(
    lines: list[str],
    node_start_lineno: int,
    ds_range: tuple[int, int],
) -> list[str]:
    """Remove docstring lines from a node's source lines list."""
    ds_start, ds_end = ds_range
    # Convert to 0-indexed relative to node start
    rel_start = ds_start - node_start_lineno
    rel_end = ds_end - node_start_lineno + 1
    return lines[:rel_start] + lines[rel_end:]


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _joined_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    src_lines: list[str],
) -> str:
    """Return the def/class signature as a single line (joins multi-line parameter lists)."""
    sig_end = node.body[0].lineno - 1 if node.body else node.end_lineno  # type: ignore[attr-defined]
    sig_lines = src_lines[node.lineno - 1 : sig_end]
    if not sig_lines:
        return src_lines[node.lineno - 1]
    if len(sig_lines) == 1:
        return sig_lines[0]
    indent = _indent_of(sig_lines[0])
    parts = [line.strip() for line in sig_lines if line.strip()]
    return indent + " ".join(parts) + "\n"


def _with_joined_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    raw_lines: list[str],
) -> list[str]:
    """Replace a multi-line signature at the start of raw_lines with a single joined line."""
    sig_len = (node.body[0].lineno - node.lineno) if node.body else len(raw_lines)  # type: ignore[attr-defined]
    if sig_len <= 1:
        return raw_lines
    indent = _indent_of(raw_lines[0])
    parts = [line.strip() for line in raw_lines[:sig_len] if line.strip()]
    joined = indent + " ".join(parts) + "\n"
    return [joined] + raw_lines[sig_len:]


def _filter_blank_lines(lines: list[str]) -> list[str]:
    """Remove blank lines from a list of source lines."""
    return [line for line in lines if line.strip()]


def _decorator_lines(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    src_lines: list[str],
) -> list[str]:
    """Return source lines for all decorators of a node, in order.

    Uses the AST decorator_list which stores every @expression directly
    above the def/class keyword (no blank line separates them from it).
    """
    if not node.decorator_list:
        return []
    first = node.decorator_list[0]
    last = node.decorator_list[-1]
    # lineno is 1-indexed; slice is 0-indexed exclusive-end
    return src_lines[first.lineno - 1 : last.end_lineno]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Inline source tags: # ++ and # ---
# ---------------------------------------------------------------------------

_PLUS_TAG_RE = re.compile(r"#\s*(\+{2,})\s*$")
_MINUS_TAG_RE = re.compile(r"#\s*(-{2,})\s*$")


def _parse_inline_tag(line: str) -> tuple[str, int] | None:
    """Detect ``# ++`` or ``# ---`` inline tags at end of a source line.

    Returns ``('++', N)`` for N plus signs, ``('--', N)`` for N minus signs,
    or ``None`` if the line carries no such tag.
    """
    stripped = line.rstrip()
    m = _PLUS_TAG_RE.search(stripped)
    if m:
        return ("++", len(m.group(1)))
    m = _MINUS_TAG_RE.search(stripped)
    if m:
        return ("--", len(m.group(1)))
    return None


def _apply_minus_tags(lines: list[str]) -> list[str]:
    """Replace ``# ---`` tagged blocks with a single placeholder comment.

    A line ending with ``# ---`` (N dashes, N >= 2) causes that line and the
    next N-1 lines to be removed and replaced with ``<indent># ---``.
    """
    out: list[str] = []
    skip_until = -1
    for i, line in enumerate(lines):
        if i <= skip_until:
            continue
        tag_info = _parse_inline_tag(line)
        if tag_info and tag_info[0] == "--":
            N = tag_info[1]
            skip_until = i + N - 1
            tag_indent = _indent_of(line)
            out.append(f"{tag_indent}# {'-' * N}\n")
        else:
            out.append(line)
    return out


# ---------------------------------------------------------------------------
# Render a single function/method node
# ---------------------------------------------------------------------------


def render_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    src_lines: list[str],
    tag: str,
    text_replacement: str | None = None,
    rm_empty_lines: bool = False,
    rm_empty_lines_docs: bool = False,
) -> list[str] | None:
    """Render a function node according to tag. Returns list of lines or None if excluded."""
    if tag == "exclude":
        return None

    raw_lines = _source_lines(node, src_lines)
    sig_line = _joined_signature(node, src_lines)
    indent = _indent_of(sig_line)
    ds_range = _docstring_line_range(node)
    dec_lines = _decorator_lines(node, src_lines)

    if text_replacement is not None:
        lines_out = dec_lines + [sig_line.rstrip("\n") + "\n"]
        for text_line in text_replacement.split("\n"):
            if rm_empty_lines_docs and not text_line.strip():
                continue
            lines_out.append(f"{indent}    # {text_line}\n")
        if rm_empty_lines_docs:
            lines_out.append(f"{indent}    # ...\n")  # body placeholder
        return lines_out

    if tag == "include":
        result = _with_joined_signature(node, raw_lines)
        result = _apply_minus_tags(result)
        if rm_empty_lines:
            result = _filter_blank_lines(result)
        return dec_lines + result

    if tag == "code":
        if ds_range:
            stripped = _strip_docstring_from_lines(raw_lines, node.lineno, ds_range)
        else:
            stripped = raw_lines
        result = _with_joined_signature(node, stripped)
        result = _apply_minus_tags(result)
        if rm_empty_lines:
            result = _filter_blank_lines(result)
        return dec_lines + result

    if tag == "docs":
        # Show signature + docstring + # ... if docstring present, else full code.
        if ds_range:
            ds_node = _get_docstring_node(node)
            assert ds_node is not None
            ds_lines = src_lines[ds_node.lineno - 1 : ds_node.end_lineno]  # type: ignore[attr-defined]
            if rm_empty_lines_docs:
                ds_lines = [l for l in ds_lines if l.strip()]
            result = dec_lines + [sig_line]
            result.extend(ds_lines)

            # Check for # ++ in function body (lines after docstring).
            # If found, show N lines from the tagged line instead of just # ...
            body_start = ds_node.end_lineno - node.lineno + 1  # type: ignore[attr-defined]
            body_src = raw_lines[body_start:]
            plus_window: list[str] | None = None
            all_covered = False
            for i, bline in enumerate(body_src):
                ti = _parse_inline_tag(bline)
                if ti and ti[0] == "++":
                    N = ti[1]
                    plus_window = body_src[i : i + N]
                    all_covered = (i + N) >= len(body_src)
                    if i > 0:
                        result.append(f"{indent}    # ...\n")
                    break

            if plus_window is not None:
                result.extend(plus_window)
                if not all_covered:
                    result.append(f"{indent}    # ...\n")
            else:
                result.append(f"{indent}    # ...\n")
            return result

        # No docstring: show full body, applying # --- tags
        result = _with_joined_signature(node, raw_lines)
        result = _apply_minus_tags(result)
        if rm_empty_lines:
            result = _filter_blank_lines(result)
        return dec_lines + result

    # Fallback
    return dec_lines + _apply_minus_tags(raw_lines)


# ---------------------------------------------------------------------------
# Render a class node
# ---------------------------------------------------------------------------


def render_class(
    node: ast.ClassDef,
    src_lines: list[str],
    class_tag: str,
    method_configs: dict[str, Any],
    text_replacement: str | None = None,
    rm_empty_lines: bool = False,
    rm_empty_lines_docs: bool = False,
) -> list[str] | None:
    """Render a class node. method_configs maps method name -> (tag, text, children)."""
    if class_tag == "exclude":
        return None

    sig_line = _joined_signature(node, src_lines)
    indent = _indent_of(sig_line)
    dec_lines = _decorator_lines(node, src_lines)

    result: list[str] = dec_lines + [sig_line]
    has_preamble = False  # tracks whether anything was added after sig_line

    if text_replacement is not None:
        # text_replacement is a docstring substitute; render as comment, then fall through
        # to method rendering so unlisted methods are still shown.
        for text_line in text_replacement.split("\n"):
            if rm_empty_lines_docs and not text_line.strip():
                continue
            result.append(f"{indent}    # {text_line}\n")
        has_preamble = True
    else:
        # Class docstring (if class_tag is docs or include)
        ds_range = _docstring_line_range(node)
        if ds_range and class_tag in ("docs", "include"):
            ds_node = _get_docstring_node(node)
            assert ds_node is not None
            ds_src = src_lines[ds_node.lineno - 1 : ds_node.end_lineno]  # type: ignore[attr-defined]
            if rm_empty_lines_docs:
                ds_src = [l for l in ds_src if l.strip()]
            result.extend(ds_src)
            has_preamble = True

        # Class attribute placeholder: # ... when rm_empty_lines_docs, there IS a class
        # docstring (so we're in summary mode), and the class body has assignments.
        # Without a docstring the full body is shown anyway — no placeholder needed.
        if (
            rm_empty_lines_docs
            and class_tag in ("docs", "include")
            and ds_range is not None
        ):
            has_assigns = any(
                isinstance(item, (ast.Assign, ast.AnnAssign)) for item in node.body
            )
            if has_assigns:
                result.append(f"{indent}    # ...\n")
                # Add a blank line after # ... when triggered by annotated fields (AnnAssign),
                # since those typically represent dataclass fields separated from methods.
                has_ann_assign = any(
                    isinstance(item, ast.AnnAssign) for item in node.body
                )
                if has_ann_assign:
                    result.append("\n")
                has_preamble = True

    # Collect methods from the class body
    methods_rendered: list[list[str]] = []
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = item.name
        if name in method_configs:
            m_tag, m_text, _ = method_configs[name]
            effective_tag = m_tag if m_tag is not None else class_tag
        else:
            effective_tag = class_tag
            m_text = None

        rendered = render_function(
            item, src_lines, effective_tag, m_text, rm_empty_lines, rm_empty_lines_docs
        )
        if rendered is not None:
            methods_rendered.append(rendered)

    if methods_rendered:
        for i, m_lines in enumerate(methods_rendered):
            if i == 0 and text_replacement is not None and has_preamble:
                # Blank line between text_replacement comment and first method
                result.append("\n")
            elif i > 0:
                result.append("\n")
            result.extend(m_lines)
    else:
        # Nothing to show inside the class
        ds_range = _docstring_line_range(node) if text_replacement is None else None
        if not has_preamble:
            result.append(f"{indent}    ...\n")
        elif not ds_range or class_tag not in ("docs", "include"):
            if text_replacement is None:
                result.append(f"{indent}    ...\n")

    return result


# ---------------------------------------------------------------------------
# File-level rendering
# ---------------------------------------------------------------------------


def _parse_file_symbol_config(
    file_cfg: dict[str, Any],
) -> tuple[
    dict[str, tuple[str | None, str | None, Any]],
    dict[str, tuple[str | None, str | None, Any]],
]:
    """Parse a file-level symbol config dict into (class_configs, func_configs).

    Each entry maps name -> (tag, text, children_dict).
    """
    class_cfg_raw = file_cfg.get("class", {}) or {}
    func_cfg_raw = file_cfg.get("def", {}) or {}

    def _parse_symbol(
        raw: dict[str, Any],
    ) -> dict[str, tuple[str | None, str | None, Any]]:
        out: dict[str, tuple[str | None, str | None, Any]] = {}
        for name, val in raw.items():
            tag, text, children = parse_entry_value(val)
            out[name] = (tag, text, children)
        return out

    return _parse_symbol(class_cfg_raw), _parse_symbol(func_cfg_raw)


def render_python_file(
    path: Path,
    file_cfg: dict[str, Any] | None,
    inherited_tag: str,
    rm_empty_lines: bool = False,
    rm_empty_lines_docs: bool = False,
) -> str:
    """Render a Python file to a string according to config and inherited tag.

    file_cfg is the parsed file-level dict (may have class:/def: keys) or None.
    """
    src = path.read_text(encoding="utf-8")
    src_lines = src.splitlines(keepends=True)

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        # Fall back to raw include
        return src

    # If no symbol-level config, apply file tag uniformly
    if not file_cfg or (not file_cfg.get("class") and not file_cfg.get("def")):
        effective_tag = inherited_tag
        if effective_tag == "exclude":
            return ""
        if effective_tag == "include":
            return src
        # For code/docs at file level, apply to every top-level symbol
        # and pass through non-symbol code
        return _render_file_with_tag(
            tree, src_lines, effective_tag, rm_empty_lines, rm_empty_lines_docs
        )

    class_configs, func_configs = _parse_file_symbol_config(file_cfg)
    return _render_file_with_symbol_config(
        tree,
        src_lines,
        inherited_tag,
        class_configs,
        func_configs,
        rm_empty_lines,
        rm_empty_lines_docs,
    )


def _render_file_with_tag(
    tree: ast.Module,
    src_lines: list[str],
    tag: str,
    rm_empty_lines: bool = False,
    rm_empty_lines_docs: bool = False,
) -> str:
    """Apply a single tag to all top-level classes and functions."""
    output_lines: list[str] = []
    last_was_symbol = False
    is_first_node = True

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rendered = render_function(
                node,
                src_lines,
                tag,
                rm_empty_lines=rm_empty_lines,
                rm_empty_lines_docs=rm_empty_lines_docs,
            )
            if rendered:
                if output_lines:
                    output_lines.append("\n")
                output_lines.extend(rendered)
                last_was_symbol = True
        elif isinstance(node, ast.ClassDef):
            rendered = render_class(
                node,
                src_lines,
                tag,
                {},
                rm_empty_lines=rm_empty_lines,
                rm_empty_lines_docs=rm_empty_lines_docs,
            )
            if rendered:
                if output_lines:
                    output_lines.append("\n")
                output_lines.extend(rendered)
                last_was_symbol = True
        else:
            # Skip module-level docstring when tag is "code" (docstrings are stripped)
            if tag == "code" and _is_module_docstring(node, is_first_node):
                is_first_node = False
                continue
            # Non-symbol lines (imports, assignments, etc.)
            if last_was_symbol:
                output_lines.append("\n")
            node_lines = _source_lines(node, src_lines)
            if rm_empty_lines:
                node_lines = _filter_blank_lines(node_lines)
            output_lines.extend(node_lines)
            last_was_symbol = False
        is_first_node = False

    if last_was_symbol:
        output_lines.append("\n")

    return "".join(output_lines)


def _is_module_docstring(node: ast.AST, is_first: bool) -> bool:
    """Return True if this is the module-level docstring (first ast.Expr with a string constant)."""
    return (
        is_first
        and isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _render_file_with_symbol_config(
    tree: ast.Module,
    src_lines: list[str],
    inherited_tag: str,
    class_configs: dict[str, tuple[str | None, str | None, Any]],
    func_configs: dict[str, tuple[str | None, str | None, Any]],
    rm_empty_lines: bool = False,
    rm_empty_lines_docs: bool = False,
) -> str:
    output_lines: list[str] = []
    last_was_symbol = False

    # File-level code compression: replace non-symbol non-module-docstring code with # ...
    # Applies when rm_empty_lines_docs is True AND the file has a module docstring.
    has_module_docstring = bool(ast.get_docstring(tree))
    compress_non_symbol = (
        rm_empty_lines_docs
        and has_module_docstring
        and (bool(func_configs) or bool(class_configs))
        and inherited_tag == "docs"
    )
    pending_compress = False
    is_first_node = True
    # 1-indexed source line up to which non-symbol nodes are shown (set by # ++ tag)
    non_symbol_show_until: int = 0

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            name = node.name
            if name in class_configs:
                c_tag, c_text, c_children = class_configs[name]
                effective_tag = c_tag if c_tag is not None else inherited_tag
                # Build method configs from c_children
                method_configs: dict[str, tuple[str | None, str | None, Any]] = {}
                if c_children and isinstance(c_children, dict):
                    raw_methods = c_children.get("def", {}) or {}
                    for mname, mval in raw_methods.items():
                        method_configs[mname] = parse_entry_value(mval)
                rendered = render_class(
                    node,
                    src_lines,
                    effective_tag,
                    method_configs,
                    c_text,
                    rm_empty_lines,
                    rm_empty_lines_docs,
                )
            else:
                rendered = render_class(
                    node,
                    src_lines,
                    inherited_tag,
                    {},
                    rm_empty_lines=rm_empty_lines,
                    rm_empty_lines_docs=rm_empty_lines_docs,
                )
            if rendered:
                if pending_compress:
                    output_lines.append("# ...\n")
                    pending_compress = False
                if output_lines:
                    output_lines.append("\n")
                output_lines.extend(rendered)
                last_was_symbol = True

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name in func_configs:
                f_tag, f_text, _ = func_configs[name]
                effective_tag = f_tag if f_tag is not None else inherited_tag
                rendered = render_function(
                    node,
                    src_lines,
                    effective_tag,
                    f_text,
                    rm_empty_lines,
                    rm_empty_lines_docs,
                )
            else:
                rendered = render_function(
                    node,
                    src_lines,
                    inherited_tag,
                    rm_empty_lines=rm_empty_lines,
                    rm_empty_lines_docs=rm_empty_lines_docs,
                )
            if rendered:
                if pending_compress:
                    output_lines.append("# ...\n")
                    pending_compress = False
                if output_lines:
                    output_lines.append("\n")
                output_lines.extend(rendered)
                last_was_symbol = True

        else:
            # Non-symbol (imports, module docstring, assignments, etc.)
            if compress_non_symbol and not _is_module_docstring(node, is_first_node):
                node_lines = _source_lines(node, src_lines)
                node_lineno: int = node.lineno  # type: ignore[attr-defined]

                if node_lineno <= non_symbol_show_until:
                    # Within a previous # ++ window: show this node
                    if pending_compress:
                        output_lines.append("# ...\n")
                        pending_compress = False
                    if last_was_symbol:
                        output_lines.append("\n")
                    output_lines.extend(node_lines)
                    last_was_symbol = False
                else:
                    # Check if this node itself contains a # ++ tag
                    plus_found = False
                    for i, nline in enumerate(node_lines):
                        ti = _parse_inline_tag(nline)
                        if ti and ti[0] == "++":
                            N = ti[1]
                            non_symbol_show_until = node_lineno + i + N - 1
                            plus_found = True
                            break

                    if plus_found:
                        if pending_compress:
                            output_lines.append("# ...\n")
                            pending_compress = False
                        if last_was_symbol:
                            output_lines.append("\n")
                        output_lines.extend(node_lines)
                        last_was_symbol = False
                    else:
                        pending_compress = True
            else:
                if last_was_symbol:
                    output_lines.append("\n")
                node_lines = _source_lines(node, src_lines)
                if rm_empty_lines:
                    node_lines = _filter_blank_lines(node_lines)
                output_lines.extend(node_lines)
                last_was_symbol = False

        is_first_node = False

    if pending_compress:
        if last_was_symbol or output_lines:
            output_lines.append("\n")
        output_lines.append("# ...\n")
    elif last_was_symbol:
        output_lines.append("\n")

    return "".join(output_lines)
