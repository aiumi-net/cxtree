"""Tests for context_tree/yaml_io.py"""

from __future__ import annotations

from pathlib import Path

import pytest

from cxtree.models import Config
from cxtree.yaml_io import (_QuotedStr, _requote_entry_values,
                            _serialize_dir_entry, build_root_abstract,
                            load_yaml, parse_root_abstract, save_yaml)

# ---------------------------------------------------------------------------
# load_yaml
# ---------------------------------------------------------------------------


class TestLoadYaml:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        result = load_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_valid_yaml_roundtrip(self, tmp_path: Path):
        f = tmp_path / "data.yaml"
        f.write_text("key: value\nnumber: 42\n", encoding="utf-8")
        data = load_yaml(f)
        assert data == {"key": "value", "number": 42}

    def test_non_dict_yaml_returns_empty(self, tmp_path: Path):
        f = tmp_path / "list.yaml"
        f.write_text("- a\n- b\n", encoding="utf-8")
        assert load_yaml(f) == {}

    def test_invalid_yaml_raises_value_error(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: {unclosed\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_yaml(f)


# ---------------------------------------------------------------------------
# save_yaml + load_yaml roundtrip for root abstract
# ---------------------------------------------------------------------------


class TestSaveLoadRootAbstract:
    def test_roundtrip(self, tmp_path: Path):
        config = Config()
        entries = {
            "src": {"is_dir": True, "module.py": "docs"},
        }
        data = build_root_abstract(config=config, root_tag="docs", entries=entries)
        path = tmp_path / "abstract-tree.yaml"
        save_yaml(path, data)
        loaded = load_yaml(path)
        assert "cxtree" in loaded

    def test_parse_after_save(self, tmp_path: Path):
        config = Config(include_extensions=["py", "toml"])
        entries = {}
        data = build_root_abstract(config=config, root_tag="code", entries=entries)
        path = tmp_path / "abstract-tree.yaml"
        save_yaml(path, data)

        loaded = load_yaml(path)
        config2, root_tag2, entries2 = parse_root_abstract(loaded)
        assert root_tag2 == "code"
        assert "py" in config2.include_extensions
        assert "toml" in config2.include_extensions


# ---------------------------------------------------------------------------
# build_root_abstract / parse_root_abstract round-trip
# ---------------------------------------------------------------------------


class TestBuildParseRoundtrip:
    def test_basic_roundtrip(self):
        config = Config(rm_empty_lines=True, rm_empty_lines_docs=False)
        entries = {"mydir": {"is_dir": True}}
        data = build_root_abstract(config=config, root_tag="include", entries=entries)
        config2, root_tag, entries2 = parse_root_abstract(data)
        assert root_tag == "include"
        assert config2.rm_empty_lines is True
        assert config2.rm_empty_lines_docs is False
        assert "mydir" in entries2

    def test_ext_found_preserved(self):
        config = Config(ext_found=["py", "toml"])
        data = build_root_abstract(config=config, root_tag="docs", entries={})
        config2, _, _ = parse_root_abstract(data)
        assert "py" in config2.ext_found
        assert "toml" in config2.ext_found

    def test_is_flat_preserved(self):
        config = Config(is_flat=False)
        data = build_root_abstract(config=config, root_tag="docs", entries={})
        config2, _, _ = parse_root_abstract(data)
        assert config2.is_flat is False


# ---------------------------------------------------------------------------
# _requote_entry_values
# ---------------------------------------------------------------------------


class TestRequoteEntryValues:
    def test_non_tag_string_becomes_quoted(self):
        result = _requote_entry_values("hello world")
        assert isinstance(result, _QuotedStr)

    def test_tag_string_stays_plain(self):
        for tag in ("docs", "code", "include", "exclude"):
            result = _requote_entry_values(tag)
            assert not isinstance(result, _QuotedStr)
            assert result == tag

    def test_none_passthrough(self):
        assert _requote_entry_values(None) is None

    def test_dict_recursive(self):
        data = {"key": "some description", "tag": "docs"}
        result = _requote_entry_values(data)
        assert isinstance(result["key"], _QuotedStr)
        assert not isinstance(result["tag"], _QuotedStr)

    def test_list_recursive(self):
        data = ["line one", "docs", "line two"]
        result = _requote_entry_values(data)
        assert isinstance(result[0], _QuotedStr)
        assert not isinstance(result[1], _QuotedStr)
        assert isinstance(result[2], _QuotedStr)


# ---------------------------------------------------------------------------
# _serialize_dir_entry
# ---------------------------------------------------------------------------


class TestSerializeDirEntry:
    def test_simple_scalar_value(self):
        text = _serialize_dir_entry("mydir", "docs")
        assert "mydir:" in text
        assert "docs" in text

    def test_dir_with_file_entries(self):
        value = {
            "file1.py": "docs",
            "file2.py": "include",
        }
        text = _serialize_dir_entry("src", value)
        assert "src:" in text
        assert "file1.py:" in text
        assert "file2.py:" in text

    def test_preamble_keys_first(self):
        value = {
            "x_abstract": "docs",
            "module.py": "include",
        }
        text = _serialize_dir_entry("src", value)
        assert "x_abstract:" in text
        assert "module.py:" in text
        # preamble should appear before file entries
        assert text.index("x_abstract:") < text.index("module.py:")

    def test_non_dict_passthrough(self):
        text = _serialize_dir_entry("mydir", None)
        assert "mydir:" in text


# ---------------------------------------------------------------------------
# save_yaml for child abstract
# ---------------------------------------------------------------------------


class TestSaveChildAbstract:
    def test_child_abstract_format(self, tmp_path: Path):
        data = {
            "abstract-depth": 1,
            "parent-dirs": ["src"],
            "module.py": "docs",
        }
        path = tmp_path / "abstract.yaml"
        save_yaml(path, data)
        text = path.read_text()
        assert "abstract-depth: 1" in text
        assert "module.py:" in text

    def test_child_abstract_load_roundtrip(self, tmp_path: Path):
        data = {
            "abstract-depth": 2,
            "parent-dirs": ["domain", "users"],
            "service.py": "code",
        }
        path = tmp_path / "abstract.yaml"
        save_yaml(path, data)
        loaded = load_yaml(path)
        assert loaded["abstract-depth"] == 2
        assert loaded["parent-dirs"] == ["domain", "users"]
        assert loaded["service.py"] == "code"
