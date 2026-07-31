import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import OperationalError, UsageError

ENV_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ENGINES = ("postgresql", "mysql", "sqlite", "mssql", "oracle", "db2")

DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "sqlite": None,
    "mssql": 1433,
    "oracle": 1521,
    "db2": 50000,
}

DEFAULT_CHARSETS = {
    "mysql": "utf8mb4",
    "postgresql": "UTF8",
    "db2": "UTF8",
    "oracle": "AL32UTF8",
    "mssql": None,
    "sqlite": None,
}

FIELD_ENV_MAP = {
    "engine": "PSMT_ENGINE",
    "server": "PSMT_SERVER",
    "port": "PSMT_PORT",
    "user": "PSMT_USER",
    "password": "PSMT_PASSWORD",
    "database": "PSMT_DATABASE",
    "charset": "PSMT_CHARSET",
    "auth": "PSMT_AUTH",
    "auth_params.method": "PSMT_AUTH_METHOD",
    "auth_params.client_id": "PSMT_AUTH_CLIENT_ID",
    "auth_params.client_secret": "PSMT_AUTH_CLIENT_SECRET",
    "auth_params.tenant_id": "PSMT_AUTH_TENANT_ID",
    "connection_string": "PSMT_CONNECTION_STRING",
    "migrations_dir": "PSMT_DIR",
}

SELECTION_ENV_VARS = ("PSMT_DB", "PSMT_ENV", "PSMT_VERBOSE", "NO_COLOR")


@dataclass
class DatabaseConfig:
    engine: str = "postgresql"
    server: str = "localhost"
    port: int = 0
    user: str = None
    password: str = None
    database: str = None
    connection_string: str = None
    charset: str = None
    auth: str = "password"
    auth_params: dict = field(default_factory=dict)
    migrations_dir: str = "./migrations"
    transaction_strip: bool = False
    transaction_strip_patterns: list = field(default_factory=list)

    def __post_init__(self):
        if not self.port:
            self.port = DEFAULT_PORTS.get(self.engine) or 0
        if self.charset is None:
            self.charset = DEFAULT_CHARSETS.get(self.engine)


def validate_env(env):
    if not env or not ENV_NAME_RE.match(env):
        raise UsageError(f"invalid environment name: {env}")


def dotenv_name(env):
    return ".env" if env == "default" else f".env.{env}"


def find_config_file(env, start=None):
    start = Path(start) if start else Path.cwd()
    start = start.resolve()
    for level in [start, *start.parents]:
        cfg_dir = level / "config"
        for fname in (f"{env}.yml", f"{env}.json", dotenv_name(env)):
            p = cfg_dir / fname
            if p.is_file():
                return p
    return None


def parse_dotenv(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _dotenv_to_named(dotenv):
    cfg = {}
    for key, value in dotenv.items():
        if key in SELECTION_ENV_VARS or not key.startswith("PSMT_"):
            continue
        field_name = _env_to_field(key)
        if field_name is None:
            continue
        _assign(cfg, field_name, _coerce(field_name, value))
    return cfg


def _env_to_field(env_name):
    for field_name, env in FIELD_ENV_MAP.items():
        if env == env_name:
            return field_name
    return None


def _coerce(field_name, value):
    if field_name == "port":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if field_name == "auth_params.method":
        return value
    return value


def _assign(cfg, dotted, value):
    parts = dotted.split(".")
    target = cfg
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def load_config_file(env, start=None, environ=None):
    validate_env(env)
    p = find_config_file(env, start)
    if p is None:
        raise OperationalError(f"config file not found: config/{env}.yml")
    suffix = p.suffix.lower()
    if suffix == ".yml":
        import yaml

        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    elif suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
    else:
        dotenv = parse_dotenv(p.read_text(encoding="utf-8"))
        data = {"default": _dotenv_to_named(dotenv)}
    if not isinstance(data, dict):
        raise OperationalError(f"invalid config file: {p}")
    return data


def resolve_database_config(env, db_key="default", cli_dir=None, start=None, environ=None):
    environ = environ if environ is not None else os.environ
    raw = load_config_file(env, start, environ)
    if db_key not in raw:
        raise OperationalError(f"database config not found: {db_key}")
    cfg = raw.get(db_key) or {}
    if not isinstance(cfg, dict):
        raise OperationalError(f"database config not found: {db_key}")
    engine = _first(environ.get("PSMT_ENGINE"), cfg.get("engine"), "postgresql")
    if engine not in ENGINES:
        raise OperationalError(f"unknown engine: {engine}")

    if cfg.get("user") == "/" and engine != "oracle":
        raise OperationalError('user: "/" (SYSDBA) is valid only for the oracle engine')

    conn_string = _first(environ.get("PSMT_CONNECTION_STRING"), cfg.get("connection_string"))

    result = DatabaseConfig(engine=engine)
    if conn_string:
        result.connection_string = conn_string
        result.database = _first(environ.get("PSMT_DATABASE"), cfg.get("database"))
        result.migrations_dir = _first(
            environ.get("PSMT_DIR"), cfg.get("migrations_dir"), "./migrations"
        )
    else:
        result.server = _first(environ.get("PSMT_SERVER"), cfg.get("server"), "localhost")
        port = _coerce("port", _first(environ.get("PSMT_PORT"), cfg.get("port")))
        if port:
            result.port = port
        result.user = _first(environ.get("PSMT_USER"), cfg.get("user"))
        result.password = _first(environ.get("PSMT_PASSWORD"), cfg.get("password"))
        result.database = _first(environ.get("PSMT_DATABASE"), cfg.get("database"))
        result.charset = _first(
            environ.get("PSMT_CHARSET"), cfg.get("charset"), DEFAULT_CHARSETS.get(engine)
        )
        result.migrations_dir = _first(
            environ.get("PSMT_DIR"), cfg.get("migrations_dir"), "./migrations"
        )

    result.auth = _first(environ.get("PSMT_AUTH"), cfg.get("auth"), "password")
    auth_params = dict(cfg.get("auth_params") or {})
    for field_name, env_var in (
        ("method", "PSMT_AUTH_METHOD"),
        ("client_id", "PSMT_AUTH_CLIENT_ID"),
        ("client_secret", "PSMT_AUTH_CLIENT_SECRET"),
        ("tenant_id", "PSMT_AUTH_TENANT_ID"),
    ):
        if env_var in environ:
            auth_params[field_name] = environ[env_var]
        elif field_name not in auth_params and field_name in cfg.get("auth_params", {}):
            auth_params[field_name] = cfg["auth_params"][field_name]
    result.auth_params = auth_params

    strip = cfg.get("transaction", {}).get("strip", False)
    if environ.get("PSMT_TRANSACTION_STRIP") is not None:
        strip = environ["PSMT_TRANSACTION_STRIP"].strip().lower() == "true"
    result.transaction_strip = bool(strip)
    patterns = cfg.get("transaction", {}).get("strip_patterns")
    if isinstance(patterns, list):
        result.transaction_strip_patterns = list(patterns)

    if cli_dir:
        result.migrations_dir = cli_dir
    return result


def _first(*values):
    for value in values:
        if value is not None:
            return value
    return None


def select_env(env_flag, environ=None):
    environ = environ if environ is not None else os.environ
    return env_flag if env_flag is not None else environ.get("PSMT_ENV", "default")


def select_db(db_flag, env_flag, positional=None, environ=None):
    environ = environ if environ is not None else os.environ
    if positional is not None:
        return positional
    if db_flag is not None:
        return db_flag
    return environ.get("PSMT_DB", "default")
