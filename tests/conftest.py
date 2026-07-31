import os

import pytest


@pytest.fixture
def run_cli():
    from psmt.cli import main

    def _run(*argv):
        return main(list(argv))

    return _run


@pytest.fixture
def sqlite_project(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yml").write_text(
        "default:\n  engine: sqlite\n  database: app.sqlite\n  migrations_dir: ./migrations\n",
        encoding="utf-8",
    )
    (tmp_path / "migrations").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path
