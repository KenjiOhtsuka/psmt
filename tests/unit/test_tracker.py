from psmt import tracker


class TestMigrationDdl:
    def test_all_engines_present(self):
        for engine in ("sqlite", "postgresql", "mysql", "mssql", "oracle", "db2"):
            assert "_migration" in tracker.MIGRATION_DDL[engine]

    def test_sqlite_text_columns(self):
        assert "TEXT" in tracker.MIGRATION_DDL["sqlite"]

    def test_postgresql_timestamptz(self):
        assert "TIMESTAMPTZ" in tracker.MIGRATION_DDL["postgresql"]

    def test_mysql_utf8mb4(self):
        assert "utf8mb4" in tracker.MIGRATION_DDL["mysql"]

    def test_oracle_varchar2(self):
        assert "VARCHAR2" in tracker.MIGRATION_DDL["oracle"]

    def test_primary_key_columns(self):
        for engine in tracker.MIGRATION_DDL:
            assert "main_version" in tracker.MIGRATION_DDL[engine]
            assert "sub_version" in tracker.MIGRATION_DDL[engine]


class TestAppliedAtLiteral:
    UTC = "2026-01-03 22:33:44"

    def test_postgresql_explicit_offset(self):
        assert tracker.applied_at_literal("postgresql", self.UTC) == "'2026-01-03 22:33:44+00'"

    def test_oracle_to_timestamp(self):
        assert tracker.applied_at_literal("oracle", self.UTC) == (
            "TO_TIMESTAMP('2026-01-03 22:33:44','YYYY-MM-DD HH24:MI:SS')"
        )

    def test_bare_literal_engines(self):
        for engine in ("mysql", "mssql", "db2", "sqlite"):
            assert tracker.applied_at_literal(engine, self.UTC) == "'2026-01-03 22:33:44'"


class TestNowExpr:
    def test_per_engine(self):
        expected = {
            "mysql": "CURRENT_TIMESTAMP",
            "postgresql": "CURRENT_TIMESTAMP",
            "mssql": "SYSDATETIME()",
            "oracle": "SYSTIMESTAMP",
            "db2": "CURRENT TIMESTAMP",
            "sqlite": "datetime('now')",
        }
        for engine, expr in expected.items():
            assert tracker.now_expr(engine) == expr


class TestStatements:
    def test_insert_with_utc(self):
        sql = tracker.insert_statement("sqlite", "v1", "01", "2026-01-03 22:33:44")
        assert sql == (
            "INSERT INTO _migration (main_version, sub_version, applied_at) "
            "VALUES ('v1', '01', '2026-01-03 22:33:44');"
        )

    def test_insert_preview_uses_now_expr(self):
        sql = tracker.insert_statement("mssql", "v1", "01")
        assert "SYSDATETIME()" in sql

    def test_oracle_preview_uses_systimestamp(self):
        assert "SYSTIMESTAMP" in tracker.insert_statement("oracle", "v1", "01")

    def test_update(self):
        sql = tracker.update_statement("postgresql", "v1", "01", "2026-01-03 22:33:44")
        assert sql == (
            "UPDATE _migration SET applied_at = '2026-01-03 22:33:44+00' "
            "WHERE main_version = 'v1' AND sub_version = '01';"
        )

    def test_delete(self):
        sql = tracker.delete_statement("v1", "01")
        assert sql == (
            "DELETE FROM _migration "
            "WHERE main_version = 'v1' AND sub_version = '01';"
        )
