import pytest

from psmt import dbadmin

from tests.integration.helpers import (
    ENGINES,
    create_config,
    make_context,
    migrate_config,
    server_available,
)

MAIN_VERSION = "20260103223344001"
SUB_VERSION = "01"


def _write_migrations(migrations_dir):
    folder = migrations_dir / f"{MAIN_VERSION}_add_users"
    folder.mkdir(parents=True)
    (folder / f"{SUB_VERSION}_migrate__do.sql").write_text(
        "CREATE TABLE users (id INT PRIMARY KEY);\n"
        "INSERT INTO users (id) VALUES (1);\n",
        encoding="utf-8",
    )
    (folder / f"{SUB_VERSION}_migrate__undo.sql").write_text(
        "DROP TABLE users;\n",
        encoding="utf-8",
    )


def _fetch_applied(ctx):
    conn = ctx.driver.connect(ctx.cfg)
    try:
        return ctx.driver.fetch_applied(conn)
    finally:
        ctx.driver.close(conn)


def _users_rows(ctx):
    conn = ctx.driver.connect(ctx.cfg)
    try:
        return [row[0] for row in ctx.driver.query(conn, "SELECT id FROM users ORDER BY id")]
    finally:
        ctx.driver.close(conn)


@pytest.mark.integration
@pytest.mark.parametrize("engine", ENGINES)
def test_migrate_rollback_cycle(engine, tmp_path):
    if engine != "sqlite":
        reason = server_available(create_config(engine, tmp_path))
        if reason:
            pytest.skip(reason)

    create_cfg = create_config(engine, tmp_path)
    _write_migrations(create_cfg.migrations_dir)

    if engine == "db2":
        admin_ctx = None
    else:
        admin_ctx = make_context(create_cfg)
        dbadmin.run_db_create(admin_ctx)
    try:
        ctx = make_context(migrate_config(engine, create_cfg))
        from psmt.executor.migrate import run_migrate
        from psmt.executor.rollback import run_rollback

        assert run_migrate(ctx) is True
        assert _fetch_applied(ctx) == {(MAIN_VERSION, SUB_VERSION)}
        assert _users_rows(ctx) == [1]

        assert run_migrate(ctx) is True
        assert _fetch_applied(ctx) == {(MAIN_VERSION, SUB_VERSION)}

        assert run_rollback(ctx, steps=1) is True
        assert _fetch_applied(ctx) == set()
    finally:
        if admin_ctx is not None:
            dbadmin.run_db_destroy(admin_ctx)


@pytest.mark.integration
@pytest.mark.parametrize("engine", ["sqlite"])
def test_db_create_destroy(engine, tmp_path):
    cfg = create_config(engine, tmp_path)
    ctx = make_context(cfg)
    dbadmin.run_db_create(ctx)
    assert (tmp_path / "app.sqlite").is_file()
    dbadmin.run_db_destroy(ctx)
    assert not (tmp_path / "app.sqlite").exists()
