from pathlib import Path

from .exceptions import OperationalError

_DEFAULT_TABLESPACE_SQL = (
    "SELECT PROPERTY_VALUE FROM DATABASE_PROPERTIES "
    "WHERE PROPERTY_NAME = 'DEFAULT_PERMANENT_TABLESPACE'"
)


def run_db_create(ctx):
    logger = ctx.logger
    engine = ctx.cfg.engine
    driver = ctx.driver
    if engine == "sqlite":
        path = Path(ctx.cfg.database)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        logger.info(f"created database: {path}")
        return
    conn = driver.server_connect(ctx.cfg)
    try:
        driver.autocommit(conn, True)
        if engine == "oracle":
            _oracle_create_schema(ctx, conn)
        else:
            for statement in _create_database_sql(ctx.cfg):
                driver.execute(conn, statement)
    finally:
        driver.close(conn)
    logger.info(f"created database: {ctx.cfg.database}")


def run_db_destroy(ctx):
    logger = ctx.logger
    engine = ctx.cfg.engine
    driver = ctx.driver
    if engine == "sqlite":
        base = Path(ctx.cfg.database)
        for suffix in ("", "-wal", "-shm"):
            target = Path(str(base) + suffix)
            if target.exists():
                target.unlink()
        logger.info(f"destroyed database: {base}")
        return
    conn = driver.server_connect(ctx.cfg)
    try:
        driver.autocommit(conn, True)
        for statement in _drop_database_sql(ctx.cfg):
            driver.execute(conn, statement)
    finally:
        driver.close(conn)
    logger.info(f"destroyed database: {ctx.cfg.database}")


def _create_database_sql(cfg):
    database = cfg.database
    charset = cfg.charset
    if cfg.engine == "postgresql":
        return [f"CREATE DATABASE {database} ENCODING '{charset}'"]
    if cfg.engine == "mysql":
        return [f"CREATE DATABASE {database} CHARACTER SET {charset}"]
    if cfg.engine == "mssql":
        return [f"CREATE DATABASE {database}"]
    if cfg.engine == "db2":
        return [f"CREATE DATABASE {database} USING CODESET {charset}"]
    if cfg.engine == "sqlite":
        return []
    raise OperationalError(f"unknown engine: {cfg.engine}")


def _drop_database_sql(cfg):
    database = cfg.database
    if cfg.engine == "postgresql":
        return [f"DROP DATABASE {database}"]
    if cfg.engine == "mysql":
        return [f"DROP DATABASE {database}"]
    if cfg.engine == "mssql":
        return [f"DROP DATABASE {database}"]
    if cfg.engine == "db2":
        return [f"DROP DATABASE {database}"]
    if cfg.engine == "oracle":
        return [f"DROP USER {database} CASCADE"]
    if cfg.engine == "sqlite":
        return []
    raise OperationalError(f"unknown engine: {cfg.engine}")


def _oracle_create_schema(ctx, conn):
    if (ctx.cfg.user or "") != "/":
        raise OperationalError('oracle db create requires user: "/" (SYSDBA)')
    if not ctx.cfg.password:
        raise OperationalError("oracle db create requires a password for the new schema")
    database = ctx.cfg.database
    rows = ctx.driver.query(conn, _DEFAULT_TABLESPACE_SQL)
    if not rows:
        raise OperationalError("could not determine the instance default tablespace")
    tablespace = rows[0][0]
    statements = [
        f"CREATE USER {database} IDENTIFIED BY {ctx.cfg.password}",
        f"GRANT CONNECT, RESOURCE TO {database}",
        f"ALTER USER {database} QUOTA UNLIMITED ON {tablespace}",
    ]
    for statement in statements:
        ctx.driver.execute(conn, statement)
