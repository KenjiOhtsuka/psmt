import pytest

from psmt import __version__


class TestExitCodes:
    def test_init_creates_skeleton(self, tmp_path, monkeypatch, run_cli):
        monkeypatch.chdir(tmp_path)
        code = run_cli("init", "-d", "./migrations")
        assert code == 0
        assert (tmp_path / "migrations").is_dir()
        for env in ("default", "dev", "prod"):
            assert (tmp_path / "config" / f"{env}.yml").is_file()

    def test_generate_creates_folder(self, sqlite_project, run_cli):
        code = run_cli("generate", "migration", "--summary", "add user")
        assert code == 0
        folders = [p.name for p in (sqlite_project / "migrations").iterdir() if p.is_dir()]
        assert len(folders) == 1
        folder = sqlite_project / "migrations" / folders[0]
        assert (folder / "01_migrate__do.sql").is_file()
        assert (folder / "01_migrate__undo.sql").is_file()

    def test_tool_version(self, run_cli, capsys):
        with pytest.raises(SystemExit) as exc:
            run_cli("--tool-version")
        assert exc.value.code == 0
        assert f"psmt {__version__}" in capsys.readouterr().out

    def test_migrate_empty_success(self, sqlite_project, run_cli):
        assert run_cli("migrate") == 0

    def test_unknown_engine(self, tmp_path, monkeypatch, run_cli):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "default.yml").write_text(
            "default:\n  engine: cassandra\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        assert run_cli("migrate") == 1

    def test_invalid_env_name(self, sqlite_project, run_cli):
        assert run_cli("migrate", "-e", "bad/env") == 2

    def test_invalid_version_flag(self, sqlite_project, run_cli):
        assert run_cli("migrate", "--version", "bad_version") == 2

    def test_version_requires_value(self, sqlite_project, run_cli):
        with pytest.raises(SystemExit) as exc:
            run_cli("migrate", "--version")
        assert exc.value.code == 2

    def test_version_and_steps_conflict(self, sqlite_project, run_cli):
        assert run_cli("migrate", "--version", "v1", "--steps", "2") == 2

    def test_preview_requires_version(self, sqlite_project, run_cli):
        assert run_cli("preview") == 2

    def test_db_destroy_requires_force(self, sqlite_project, run_cli):
        assert run_cli("db", "destroy") == 2

    def test_check_clean(self, sqlite_project, run_cli):
        assert run_cli("check", "--no-grammar") == 0

    def test_unknown_command(self, run_cli):
        with pytest.raises(SystemExit) as exc:
            run_cli("frobnicate")
        assert exc.value.code == 2


class TestMigrations:
    def test_full_cycle(self, sqlite_project, run_cli):
        assert run_cli("generate", "--summary", "add user") == 0
        folder = next(p for p in (sqlite_project / "migrations").iterdir() if p.is_dir())
        (folder / "01_migrate__do.sql").write_text("CREATE TABLE users (id INTEGER PRIMARY KEY);")
        (folder / "01_migrate__undo.sql").write_text("DROP TABLE users;")
        main = folder.name.split("_", 1)[0]

        assert run_cli("migrate") == 0
        assert run_cli("versions") == 0
        assert run_cli("preview", f"{main}:01") == 0
        assert run_cli("check", "--no-grammar") == 0
        assert run_cli("rollback") == 0
        assert run_cli("migrate") == 0

    def test_generate_db_key(self, sqlite_project, run_cli):
        code = run_cli("generate", "default", "--summary", "x")
        assert code == 0
