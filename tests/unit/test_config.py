import pytest

from psmt import config as config_mod
from psmt.exceptions import OperationalError, UsageError

SQLITE_CONFIG = """default:
  engine: sqlite
  database: myapp.sqlite
  migrations_dir: ./migrations
"""


def write_config(tmp_path, content=SQLITE_CONFIG, env="default", fmt="yml"):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    fname = config_mod.dotenv_name(env) if fmt == "env" else f"{env}.{fmt}"
    path = cfg_dir / fname
    path.write_text(content, encoding="utf-8")
    return path


class TestEnvValidation:
    def test_valid(self):
        for name in ("default", "dev", "default.qa", "prod-x"):
            config_mod.validate_env(name)

    def test_invalid(self, tmp_path):
        with pytest.raises(UsageError):
            config_mod.validate_env("bad/env")

    def test_empty(self):
        with pytest.raises(UsageError):
            config_mod.validate_env("")


class TestDiscovery:
    def test_finds_yml(self, tmp_path, monkeypatch):
        write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        found = config_mod.find_config_file("default")
        assert found == tmp_path / "config" / "default.yml"

    def test_walks_up_to_parent(self, tmp_path, monkeypatch):
        write_config(tmp_path)
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        found = config_mod.find_config_file("default")
        assert found == tmp_path / "config" / "default.yml"

    def test_yaml_beats_json_at_same_level(self, tmp_path, monkeypatch):
        write_config(tmp_path, fmt="yml")
        write_config(tmp_path, fmt="json")
        monkeypatch.chdir(tmp_path)
        assert config_mod.find_config_file("default").suffix == ".yml"

    def test_nearest_level_wins(self, tmp_path, monkeypatch):
        write_config(tmp_path, fmt="json")
        nested = tmp_path / "a"
        nested.mkdir()
        write_config(nested, fmt="yml")
        monkeypatch.chdir(nested)
        assert config_mod.find_config_file("default") == nested / "config" / "default.yml"

    def test_dotenv_beats_parent_yaml(self, tmp_path, monkeypatch):
        write_config(tmp_path, fmt="yml")
        nested = tmp_path / "a"
        nested.mkdir()
        write_config(nested, fmt="env")
        monkeypatch.chdir(nested)
        assert config_mod.find_config_file("default").name == ".env"

    def test_env_specific_files(self, tmp_path, monkeypatch):
        write_config(tmp_path, env="prod")
        monkeypatch.chdir(tmp_path)
        assert config_mod.find_config_file("prod").name == "prod.yml"
        assert config_mod.find_config_file("dev") is None

    def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(OperationalError):
            config_mod.load_config_file("default")


class TestDotenv:
    def test_populates_default(self, tmp_path, monkeypatch):
        write_config(
            tmp_path,
            content="PSMT_ENGINE=sqlite\nPSMT_DATABASE=app.sqlite\nPSMT_DIR=./m\n",
            fmt="env",
        )
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config("default", "default", environ={})
        assert cfg.engine == "sqlite"
        assert cfg.database == "app.sqlite"
        assert cfg.migrations_dir == "./m"

    def test_selection_keys_ignored_in_dotenv(self, tmp_path, monkeypatch):
        write_config(
            tmp_path,
            content="PSMT_ENV=prod\nPSMT_DB=other\nPSMT_VERBOSE=1\nNO_COLOR=1\nPSMT_ENGINE=sqlite\n",
            fmt="env",
        )
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config("default", "default", environ={})
        assert cfg.engine == "sqlite"

    def test_env_var_overrides_dotenv_value(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="PSMT_ENGINE=sqlite\nPSMT_DATABASE=from_dotenv\n", fmt="env")
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config(
            "default", "default", environ={"PSMT_DATABASE": "from_env"}
        )
        assert cfg.database == "from_env"


class TestPrecedence:
    def test_env_overrides_config(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: sqlite\n  database: cfg_db\n")
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config(
            "default", "default", environ={"PSMT_DATABASE": "env_db"}
        )
        assert cfg.database == "env_db"

    def test_env_overrides_selected_named_config(self, tmp_path, monkeypatch):
        write_config(
            tmp_path,
            content=(
                "default:\n  engine: sqlite\n  database: d1\n"
                "other:\n  engine: sqlite\n  database: d2\n"
            ),
        )
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config(
            "default", "other", environ={"PSMT_DATABASE": "env_db"}
        )
        assert cfg.database == "env_db"

    def test_connection_string_wins_over_env(self, tmp_path, monkeypatch):
        write_config(
            tmp_path,
            content=(
                "default:\n"
                "  engine: mssql\n"
                '  connection_string: "Driver={ODBC Driver 18};Server=x;PWD=abc;"\n'
            ),
        )
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config(
            "default", "default", environ={"PSMT_PASSWORD": "other"}
        )
        assert cfg.connection_string is not None
        assert cfg.password is None

    def test_engine_default(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  database: myapp\n")
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config("default", "default", environ={})
        assert cfg.engine == "postgresql"
        assert cfg.port == 5432

    def test_unknown_engine(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: cassandra\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(OperationalError):
            config_mod.resolve_database_config("default", "default", environ={})

    def test_slash_user_only_oracle(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: mysql\n  user: /\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(OperationalError):
            config_mod.resolve_database_config("default", "default", environ={})

    def test_db_key_missing(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: sqlite\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(OperationalError):
            config_mod.resolve_database_config("default", "nope", environ={})

    def test_cli_dir_overrides_migrations_dir(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: sqlite\n  migrations_dir: ./cfg_m\n")
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config("default", "default", cli_dir="./cli_m", environ={})
        assert cfg.migrations_dir == "./cli_m"

    def test_transaction_strip_env(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: sqlite\n")
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config(
            "default", "default", environ={"PSMT_TRANSACTION_STRIP": "true"}
        )
        assert cfg.transaction_strip is True

    def test_trust_server_certificate_env_coerced(self, tmp_path, monkeypatch):
        write_config(tmp_path, content="default:\n  engine: mssql\n")
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config(
            "default",
            "default",
            environ={"PSMT_AUTH_TRUST_SERVER_CERTIFICATE": "true"},
        )
        assert cfg.auth_params["trust_server_certificate"] is True

    def test_trust_server_certificate_from_config(self, tmp_path, monkeypatch):
        write_config(
            tmp_path,
            content=(
                "default:\n"
                "  engine: mssql\n"
                "  auth_params:\n"
                "    trust_server_certificate: true\n"
            ),
        )
        monkeypatch.chdir(tmp_path)
        cfg = config_mod.resolve_database_config("default", "default", environ={})
        assert cfg.auth_params["trust_server_certificate"] is True
