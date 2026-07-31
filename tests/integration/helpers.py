import os
from copy import copy
from pathlib import Path

from psmt.config import DatabaseConfig
from psmt.drivers.registry import get_driver
from psmt.exceptions import DriverNotInstalledError
from psmt.executor import MigrationContext
from psmt.logging import Logger

ENGINES = ["sqlite", "postgresql", "mysql", "mssql", "oracle", "db2"]

DOCKER = {
    "postgresql": dict(
        engine="postgresql",
        server=os.environ.get("PSMT_TEST_SERVER_PG", "localhost"),
        port=int(os.environ.get("PSMT_TEST_PORT_PG", "5432")),
        user=os.environ.get("PSMT_TEST_USER_PG", "psmt"),
        password=os.environ.get("PSMT_TEST_PASSWORD_PG", "psmt"),
    ),
    "mysql": dict(
        engine="mysql",
        server=os.environ.get("PSMT_TEST_SERVER_MYSQL", "localhost"),
        port=int(os.environ.get("PSMT_TEST_PORT_MYSQL", "3306")),
        user=os.environ.get("PSMT_TEST_USER_MYSQL", "root"),
        password=os.environ.get("PSMT_TEST_PASSWORD_MYSQL", "root"),
        charset="utf8mb4",
    ),
    "mssql": dict(
        engine="mssql",
        server=os.environ.get("PSMT_TEST_SERVER_MSSQL", "localhost"),
        port=int(os.environ.get("PSMT_TEST_PORT_MSSQL", "1433")),
        user=os.environ.get("PSMT_TEST_USER_MSSQL", "sa"),
        password=os.environ.get("PSMT_TEST_PASSWORD_MSSQL", "PsmtTest!2026"),
    ),
    "oracle": dict(
        engine="oracle",
        server=os.environ.get("PSMT_TEST_SERVER_ORACLE", "localhost"),
        port=int(os.environ.get("PSMT_TEST_PORT_ORACLE", "1521")),
        user="/",
        password=os.environ.get("PSMT_TEST_PASSWORD_ORACLE", "oracle"),
        connection_string=os.environ.get(
            "PSMT_TEST_DSN_ORACLE", "localhost:1521/FREEPDB1"
        ),
    ),
    "db2": dict(
        engine="db2",
        server=os.environ.get("PSMT_TEST_SERVER_DB2", "localhost"),
        port=int(os.environ.get("PSMT_TEST_PORT_DB2", "50000")),
        user=os.environ.get("PSMT_TEST_USER_DB2", "db2inst1"),
        password=os.environ.get("PSMT_TEST_PASSWORD_DB2", "db2psmt"),
    ),
}

TEST_DATABASE = "psmt_itest"


def create_config(engine, tmp_path):
    if engine == "sqlite":
        return DatabaseConfig(
            engine="sqlite",
            database=str(tmp_path / "app.sqlite"),
            migrations_dir=Path(tmp_path / "migrations"),
        )
    params = dict(DOCKER[engine])
    params["database"] = TEST_DATABASE
    params["migrations_dir"] = Path(tmp_path / "migrations")
    return DatabaseConfig(**params)


def migrate_config(engine, create_cfg):
    if engine != "oracle":
        return create_cfg
    cfg = copy(create_cfg)
    cfg.user = create_cfg.database
    cfg.password = DOCKER["oracle"]["password"]
    return cfg


def make_context(cfg, env="test", db_key="default"):
    logger = Logger(verbose=0, no_color=True)
    driver = get_driver(cfg.engine)
    return MigrationContext(
        logger, env, db_key, cfg, driver, Path(cfg.migrations_dir)
    )


def server_available(cfg):
    try:
        driver = get_driver(cfg.engine)
    except DriverNotInstalledError as exc:
        return f"driver not installed: {exc}"
    try:
        conn = driver.server_connect(cfg)
    except Exception as exc:
        return f"database server unavailable: {exc}"
    try:
        driver.close(conn)
    except Exception:
        pass
    return None
