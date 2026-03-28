from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ABSTRACT_FILE, VALID_TAGS, Config

# ---------------------------------------------------------------------------
# Custom representers and dumper
# ---------------------------------------------------------------------------


class _QuotedStr(str):
    """A string value that must always be rendered with double quotes in YAML.

    Use this for docstring content so the output is clearly distinguished
    from tag keywords (docs, code, include, exclude).
    """


class _FlowList(list):
    """A list rendered as a YAML flow sequence on one line: [item1, item2, ...]"""


def _represent_none(dumper: yaml.Dumper, _data: None) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


def _represent_quoted_str(dumper: yaml.Dumper, data: _QuotedStr) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


def _represent_flow_list(dumper: yaml.Dumper, data: _FlowList) -> yaml.SequenceNode:
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


class _ContextDumper(yaml.Dumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        # Never use indentless sequences — list items are always indented under their key
        return super().increase_indent(flow=flow, indentless=False)


_ContextDumper.add_representer(type(None), _represent_none)
_ContextDumper.add_representer(_QuotedStr, _represent_quoted_str)
_ContextDumper.add_representer(_FlowList, _represent_flow_list)


def _dump(data: Any) -> str:
    return yaml.dump(
        data,
        Dumper=_ContextDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict. Returns {} on error."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file with structure-aware blank line spacing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if "cxtree" in data:
        # Re-quote non-tag string values in all entries (preserves quoting across edits)
        requoted = {
            k: (_requote_entry_values(v) if k != "cxtree" else v)
            for k, v in data.items()
        }
        text = _format_root_abstract(requoted)
    elif "abstract-depth" in data:
        # parent-dirs values are plain directory names — must NOT be re-quoted
        _no_requote = {"abstract-depth", "parent-dirs"}
        requoted = {
            k: (_requote_entry_values(v) if k not in _no_requote else v)
            for k, v in data.items()
        }
        text = _format_child_abstract(requoted)
    else:
        text = _dump(data)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------------------
# Re-quoting: restore _QuotedStr after YAML round-trip
# ---------------------------------------------------------------------------


def _requote_entry_values(data: Any) -> Any:
    """Recursively wrap non-tag string values in _QuotedStr.

    After load_yaml → save_yaml round-trips, plain strings lose their
    _QuotedStr type. This restores quoting for any string that is not a
    valid tag keyword.
    """
    if data is None:
        return data
    if isinstance(data, dict):
        return {k: _requote_entry_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_requote_entry_values(item) for item in data]
    if isinstance(data, str) and data not in VALID_TAGS:
        return _QuotedStr(data)
    return data


# ---------------------------------------------------------------------------
# Structure-aware YAML formatters
# ---------------------------------------------------------------------------


def _indent_block(text: str, spaces: int = 2) -> str:
    """Indent every non-empty line of a YAML block by *spaces* spaces."""
    pad = " " * spaces
    lines = []
    for line in text.rstrip().splitlines():
        lines.append(pad + line if line.strip() else line)
    return "\n".join(lines)


def _key_line(key: str) -> str:
    """Return the bare 'key:' line for a YAML mapping key."""
    return _dump({key: None}).splitlines()[0]


def _serialize_dir_entry(dir_key: str, dir_value: Any) -> str:
    """Serialize a directory entry.

    File entries within the directory are separated by 1 blank line.
    Non-file entries (abstract tag, subdir keys) are serialized first.
    """
    if not isinstance(dir_value, dict):
        return _dump({dir_key: dir_value}).rstrip()

    _PREAMBLE_KEYS = frozenset({"abstract", "x_abstract", "is_dir", "x_hard_abstract"})

    # Separate abstract/subdir keys from file entries
    preamble = {
        k: v for k, v in dir_value.items() if k in _PREAMBLE_KEYS or k.endswith("/")
    }
    files = {
        k: v
        for k, v in dir_value.items()
        if k not in _PREAMBLE_KEYS and not k.endswith("/")
    }

    if not files:
        return _dump({dir_key: dir_value}).rstrip()

    parts: list[str] = []

    if preamble:
        parts.append(_indent_block(_dump(preamble)))

    for fname, fvalue in files.items():
        parts.append(_indent_block(_dump({fname: fvalue})))

    # 1 blank line between parts inside a directory
    body = "\n\n".join(parts)
    return f"{_key_line(dir_key)}\n{body}"


def _format_root_abstract(data: dict[str, Any]) -> str:
    """Serialize a root abstract-tree.yaml.

    - 2 blank lines between top-level entries (cxtree block + dir keys)
    - 1 blank line between file entries within each directory
    """
    sections: list[str] = []

    for key, value in data.items():
        if key == "cxtree":
            sections.append(_dump({key: value}).rstrip())
        else:
            sections.append(_serialize_dir_entry(key, value))

    # 2 blank lines between top-level sections (\n\n\n = 2 blank lines)
    return "\n\n\n".join(sections) + "\n"


def _format_child_abstract(data: dict[str, Any]) -> str:
    """Serialize a child abstract.yaml.

    - abstract-depth header first
    - 2 blank lines between file entries
    """
    sections: list[str] = []

    for key, value in data.items():
        if key == "abstract-depth":
            sections.append(f"abstract-depth: {value}")
        else:
            sections.append(_dump({key: value}).rstrip())

    return "\n\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Root abstract-tree.yaml parsing
# ---------------------------------------------------------------------------


def is_root_abstract(data: dict[str, Any]) -> bool:
    return "cxtree" in data


def is_child_abstract(data: dict[str, Any], expected_depth: int) -> bool:
    return "abstract-depth" in data and data["abstract-depth"] == expected_depth


def parse_root_abstract(
    data: dict[str, Any],
) -> tuple[Config, str | None, dict[str, Any]]:
    """Extract (config, root_tag, entries) from root abstract data."""
    ct_block = data.get("cxtree", {}) or {}
    config_raw = ct_block.get("config", {}) or {}
    is_flat = bool(ct_block.get("is_flat", True))
    ext_found_raw = ct_block.get("ext_found", [])
    ext_found = list(ext_found_raw) if isinstance(ext_found_raw, list) else []
    config = Config.from_dict(config_raw, is_flat=is_flat, ext_found=ext_found)

    # Support both x_root (current) and legacy root key
    root_raw = ct_block.get("x_root", ct_block.get("root"))
    root_tag: str | None = None
    if isinstance(root_raw, str):
        root_tag = root_raw if root_raw in VALID_TAGS else None
    elif isinstance(root_raw, list) and root_raw:
        candidate = root_raw[0]
        root_tag = (
            candidate
            if isinstance(candidate, str) and candidate in VALID_TAGS
            else None
        )

    entries = {k: v for k, v in data.items() if k != "cxtree"}
    return config, root_tag, entries


def build_root_abstract(
    config: Config,
    root_tag: str | None,
    entries: dict[str, Any],
) -> dict[str, Any]:
    """Construct the dict structure for a root abstract-tree.yaml."""
    ct_block: dict[str, Any] = {}
    ct_block["x_root"] = root_tag
    ct_block["is_flat"] = config.is_flat
    ct_block["ext_found"] = _FlowList(config.ext_found)

    config_dict = config.to_dict()
    # Extensions as a flow list (one-liner)
    config_dict["include"]["x_extensions"] = _FlowList(
        config_dict["include"]["x_extensions"]
    )
    # Quoted strings for startswith and folders
    config_dict["exclude"]["x_startswith"] = [
        _QuotedStr(s) for s in config_dict["exclude"]["x_startswith"]
    ]
    config_dict["exclude"]["x_folders"] = [
        _QuotedStr(s) for s in config_dict["exclude"]["x_folders"]
    ]
    ct_block["config"] = config_dict

    out: dict[str, Any] = {"cxtree": ct_block}
    out.update(entries)
    return out
