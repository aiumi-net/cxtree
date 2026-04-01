from __future__ import annotations

from cxtree.config import DEFAULT_N, Config


def test_defaults():
    c = Config()
    assert c.n == DEFAULT_N
    assert "py" in c.include_extensions
    assert "." in c.exclude_startswith
    assert ".venv" in c.exclude_folders


def test_from_dict_partial():
    c = Config.from_dict({"n": 500, "include_extensions": ["ts", "js"]})
    assert c.n == 500
    assert c.include_extensions == ["ts", "js"]
    # Defaults applied for missing keys
    assert c.exclude_startswith == [".", "__"]


def test_roundtrip():
    c = Config(n=1000, include_extensions=["py", "ts"])
    c2 = Config.from_dict(c.to_dict())
    assert c2.n == 1000
    assert c2.include_extensions == ["py", "ts"]
