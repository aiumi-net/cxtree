from __future__ import annotations

from pathlib import Path

import yaml

from cxtree.config import ABSTRACT_LEAF_FILE
from cxtree.yaml_io import ensure_leaf, load_leaf, save_leaf

# ---------------------------------------------------------------------------
# load_leaf / save_leaf
# ---------------------------------------------------------------------------


def test_load_leaf_missing_file(tmp_path: Path):
    assert load_leaf(tmp_path) == {}


def test_save_load_roundtrip(tmp_path: Path):
    data = {"app.py": False, "utils/": "Utility helpers."}
    save_leaf(tmp_path, data)
    loaded = load_leaf(tmp_path)
    assert loaded["app.py"] is False
    assert loaded["utils/"] == "Utility helpers."


# ---------------------------------------------------------------------------
# ensure_leaf — creation
# ---------------------------------------------------------------------------


def test_ensure_leaf_creates_file(tmp_path: Path):
    ensure_leaf(tmp_path, ["a.py", "b.py"], ["sub"])
    leaf = load_leaf(tmp_path)
    assert leaf["a.py"] is False
    assert leaf["b.py"] is False
    assert leaf["sub/"] is False


def test_ensure_leaf_noop_when_no_entries(tmp_path: Path):
    ensure_leaf(tmp_path, [], [])
    assert not (tmp_path / ABSTRACT_LEAF_FILE).exists()


# ---------------------------------------------------------------------------
# ensure_leaf — preservation
# ---------------------------------------------------------------------------


def test_ensure_leaf_no_rewrite_when_complete(tmp_path: Path):
    """File must not be touched at all when all keys already exist."""
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    original = "a.py: false\nutils/: false\n"
    leaf_path.write_text(original, encoding="utf-8")
    mtime_before = leaf_path.stat().st_mtime_ns

    ensure_leaf(tmp_path, ["a.py"], ["utils"])

    assert leaf_path.stat().st_mtime_ns == mtime_before
    assert leaf_path.read_text(encoding="utf-8") == original


def test_ensure_leaf_preserves_block_scalar_formatting(tmp_path: Path):
    """YAML block scalar written by user must not be reformatted."""
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    original = 'a.py: false\nutils/: |\n  "User management"\n'
    leaf_path.write_text(original, encoding="utf-8")

    ensure_leaf(tmp_path, ["a.py"], ["utils"])

    assert leaf_path.read_text(encoding="utf-8") == original


def test_ensure_leaf_appends_missing_keys(tmp_path: Path):
    """New files/dirs must be appended without touching existing content."""
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    original = 'a.py: false\nutils/: "Helpers."\n'
    leaf_path.write_text(original, encoding="utf-8")

    ensure_leaf(tmp_path, ["a.py", "b.py"], ["utils"])

    text = leaf_path.read_text(encoding="utf-8")
    # Original content untouched at the top
    assert text.startswith(original)
    # New key appended
    assert "b.py: false" in text
    # Existing user summary preserved
    assert '"Helpers."' in text


def test_ensure_leaf_keeps_user_summary_value(tmp_path: Path):
    """A non-false summary must be preserved as-is after ensure_leaf appends."""
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    leaf_path.write_text('a.py: "Important module."\n', encoding="utf-8")

    ensure_leaf(tmp_path, ["a.py", "new.py"], [])

    loaded = load_leaf(tmp_path)
    assert loaded["a.py"] == "Important module."
    assert loaded["new.py"] is False


def test_ensure_leaf_does_not_add_duplicate_keys(tmp_path: Path):
    """Keys already in the file must not be written twice."""
    leaf_path = tmp_path / ABSTRACT_LEAF_FILE
    leaf_path.write_text("a.py: false\n", encoding="utf-8")

    ensure_leaf(tmp_path, ["a.py"], [])

    text = leaf_path.read_text(encoding="utf-8")
    assert text.count("a.py") == 1
