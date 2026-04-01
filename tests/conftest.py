"""Shared fixtures for cxtree tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def simple_project(tmp_path: Path) -> Path:
    """Minimal Python project: one root file and one subdirectory."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        def hello():
            '''Say hello.'''
            print("hello")
        """),
        encoding="utf-8",
    )
    subdir = tmp_path / "utils"
    subdir.mkdir()
    (subdir / "helpers.py").write_text(
        textwrap.dedent("""\
        def add(a, b):
            '''Add two numbers.'''
            return a + b
        """),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def nested_project(tmp_path: Path) -> Path:
    """Project with two levels of nesting."""
    (tmp_path / "app.py").write_text("# app root\n", encoding="utf-8")
    domain = tmp_path / "domain"
    domain.mkdir()
    (domain / "models.py").write_text(
        textwrap.dedent("""\
        class User:
            '''A user model.'''
            def get_name(self):
                '''Return user name.'''
                return self.name
        """),
        encoding="utf-8",
    )
    users = domain / "users"
    users.mkdir()
    (users / "service.py").write_text(
        textwrap.dedent("""\
        def create_user(name):
            '''Create a new user.'''
            return {'name': name}
        """),
        encoding="utf-8",
    )
    return tmp_path
