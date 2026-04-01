from __future__ import annotations

from pathlib import Path

from cxtree.config import Config
from cxtree.walker import walk_dir


def test_basic_walk(simple_project: Path):
    config = Config(include_extensions=["py"])
    files = walk_dir(simple_project, config)
    rels = {f.rel for f in files}
    assert "main.py" in rels
    assert "utils/helpers.py" in rels


def test_exclude_folders(tmp_path: Path):
    (tmp_path / "main.py").write_text("x = 1")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "lib.py").write_text("x = 2")
    config = Config(include_extensions=["py"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "main.py" in rels
    assert not any(".venv" in r for r in rels)


def test_exclude_startswith(tmp_path: Path):
    (tmp_path / "good.py").write_text("x = 1")
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / ".hidden.py").write_text("")
    config = Config(include_extensions=["py"], exclude_startswith=[".", "__"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "good.py" in rels
    assert "__init__.py" not in rels
    assert ".hidden.py" not in rels


def test_extension_filter(tmp_path: Path):
    (tmp_path / "app.py").write_text("x = 1")
    (tmp_path / "style.css").write_text("body {}")
    config = Config(include_extensions=["py"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "app.py" in rels
    assert "style.css" not in rels


def test_multiple_extensions(tmp_path: Path):
    (tmp_path / "app.py").write_text("x = 1")
    (tmp_path / "index.ts").write_text("const x = 1")
    config = Config(include_extensions=["py", "ts"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "app.py" in rels
    assert "index.ts" in rels


def test_extensionless_file_included_when_name_in_extensions(tmp_path: Path):
    """Dockerfile has no extension; matched by its full filename."""
    (tmp_path / "Dockerfile").write_text("FROM python\n")
    config = Config(include_extensions=["Dockerfile"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "Dockerfile" in rels


def test_extensionless_file_excluded_when_not_in_extensions(tmp_path: Path):
    (tmp_path / "Makefile").write_text("all:\n\t@echo done\n")
    config = Config(include_extensions=["py"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "Makefile" not in rels


def test_walk_returns_relative_paths(tmp_path: Path):
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "mod.py").write_text("x = 1")
    config = Config(include_extensions=["py"])
    files = walk_dir(tmp_path, config)
    rels = {f.rel for f in files}
    assert "pkg/mod.py" in rels
    # No absolute path leaks
    assert not any(r.startswith("/") for r in rels)


def test_walk_empty_directory(tmp_path: Path):
    config = Config(include_extensions=["py"])
    files = walk_dir(tmp_path, config)
    assert files == []
