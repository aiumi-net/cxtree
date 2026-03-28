"""Tests for context_tree/models.py"""

from __future__ import annotations

from pathlib import Path

import pytest

from cxtree.models import (ABSTRACT_TREE_FOLDER, ROOT_ABSTRACT_FILE, Config,
                           get_abstract_tree_dir, parse_entry_value)

# ---------------------------------------------------------------------------
# Config.from_dict
# ---------------------------------------------------------------------------


class TestConfigFromDict:
    def test_x_prefixed_keys(self):
        data = {
            "x_rm_empty_lines": True,
            "x_rm_empty_lines_docs": False,
            "include": {"x_extensions": ["py", "toml"]},
            "exclude": {
                "x_startswith": ["."],
                "x_folders": [".venv"],
            },
        }
        config = Config.from_dict(data)
        assert config.rm_empty_lines is True
        assert config.rm_empty_lines_docs is False
        assert config.include_extensions == ["py", "toml"]
        assert config.exclude_startswith == ["."]
        assert config.exclude_folders == [".venv"]

    def test_legacy_unprefixed_keys(self):
        """Backward compatibility: old keys without x_ prefix."""
        data = {
            "rm_empty_lines": True,
            "rm_empty_lines_docs": False,
            "include": {"extensions": ["py"]},
            "exclude": {
                "startswith": ["_"],
                "folders": ["node_modules"],
            },
        }
        config = Config.from_dict(data)
        assert config.rm_empty_lines is True
        assert config.rm_empty_lines_docs is False
        assert config.include_extensions == ["py"]
        assert config.exclude_startswith == ["_"]
        assert config.exclude_folders == ["node_modules"]

    def test_defaults_on_empty_dict(self):
        config = Config.from_dict({})
        assert config.include_extensions == ["py"]
        assert "." in config.exclude_startswith
        assert "__" in config.exclude_startswith
        assert ".venv" in config.exclude_folders

    def test_is_flat_passed_through(self):
        config = Config.from_dict({}, is_flat=False)
        assert config.is_flat is False

    def test_ext_found_passed_through(self):
        config = Config.from_dict({}, ext_found=["py", "toml"])
        assert "py" in config.ext_found
        assert "toml" in config.ext_found


# ---------------------------------------------------------------------------
# Config.to_dict
# ---------------------------------------------------------------------------


class TestConfigToDict:
    def test_produces_x_prefixed_keys(self):
        config = Config(
            rm_empty_lines=True,
            rm_empty_lines_docs=False,
            include_extensions=["py"],
            exclude_startswith=["."],
            exclude_folders=[".venv"],
        )
        d = config.to_dict()
        assert d["x_rm_empty_lines"] is True
        assert d["x_rm_empty_lines_docs"] is False
        assert d["include"]["x_extensions"] == ["py"]
        assert d["exclude"]["x_startswith"] == ["."]
        assert d["exclude"]["x_folders"] == [".venv"]

    def test_roundtrip(self):
        config = Config(rm_empty_lines=False, rm_empty_lines_docs=True)
        d = config.to_dict()
        config2 = Config.from_dict(d)
        assert config2.rm_empty_lines == config.rm_empty_lines
        assert config2.rm_empty_lines_docs == config.rm_empty_lines_docs


# ---------------------------------------------------------------------------
# parse_entry_value
# ---------------------------------------------------------------------------


class TestParseEntryValue:
    def test_none_value(self):
        tag, text, children = parse_entry_value(None)
        assert tag is None
        assert text is None
        assert children is None

    def test_tag_string(self):
        for t in ("docs", "code", "include", "exclude"):
            tag, text, children = parse_entry_value(t)
            assert tag == t
            assert text is None
            assert children is None

    def test_string_replacement(self):
        tag, text, children = parse_entry_value("This is a description")
        assert tag is None
        assert text == "This is a description"
        assert children is None

    def test_list_replacement(self):
        tag, text, children = parse_entry_value(["Line 1", "Line 2"])
        assert tag is None
        assert text == "Line 1\nLine 2"
        assert children is None

    def test_dict_with_x_abstract(self):
        value = {"x_abstract": "docs", "def": {"method": "include"}}
        tag, text, children = parse_entry_value(value)
        assert tag == "docs"
        assert text is None
        assert children is not None
        assert "def" in children

    def test_dict_with_abstract(self):
        value = {"abstract": "code", "extra": "data"}
        tag, text, children = parse_entry_value(value)
        assert tag == "code"
        assert children is not None

    def test_plain_dict(self):
        value = {"class": {"Foo": "docs"}, "def": {"bar": "include"}}
        tag, text, children = parse_entry_value(value)
        assert tag is None
        assert text is None
        assert children == value


# ---------------------------------------------------------------------------
# get_abstract_tree_dir
# ---------------------------------------------------------------------------


class TestGetAbstractTreeDir:
    def test_normal_mode_returns_root(self, tmp_path: Path):
        (tmp_path / ROOT_ABSTRACT_FILE).write_text("cxtree:\n", encoding="utf-8")
        result = get_abstract_tree_dir(tmp_path)
        assert result == tmp_path

    def test_folder_mode_returns_subfolder(self, tmp_path: Path):
        folder = tmp_path / ABSTRACT_TREE_FOLDER
        folder.mkdir()
        (folder / ROOT_ABSTRACT_FILE).write_text("cxtree:\n", encoding="utf-8")
        result = get_abstract_tree_dir(tmp_path)
        assert result == folder

    def test_no_config_returns_root(self, tmp_path: Path):
        result = get_abstract_tree_dir(tmp_path)
        assert result == tmp_path
