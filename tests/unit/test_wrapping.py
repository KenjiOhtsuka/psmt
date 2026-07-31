import pytest

from psmt import wrapping
from psmt.wrapping import (
    detect_non_transactional,
    process_file,
    strip_transaction_controls,
    wrap_content,
)


class TestStripTransactionControls:
    def test_bare_begin_stripped_on_sqlite(self):
        content = "BEGIN;\nSELECT 1;\nCOMMIT;"
        result = strip_transaction_controls(content, "sqlite")
        assert result.strip() == "SELECT 1;"

    def test_bare_begin_not_stripped_on_mysql(self):
        content = "BEGIN;\nSELECT 1;"
        result = strip_transaction_controls(content, "mysql")
        assert result == content

    def test_begin_work_stripped_on_mysql(self):
        content = "BEGIN WORK;\nSELECT 1;"
        result = strip_transaction_controls(content, "mysql")
        assert result.strip() == "SELECT 1;"

    def test_bare_begin_not_stripped_on_oracle(self):
        content = "BEGIN\n  NULL;\nEND;"
        assert strip_transaction_controls(content, "oracle") == content

    def test_bare_begin_not_stripped_on_db2(self):
        content = "BEGIN ATOMIC\n  SELECT 1;\nEND"
        assert strip_transaction_controls(content, "db2") == content

    def test_start_transaction_stripped(self):
        content = "START TRANSACTION;\nSELECT 1;"
        result = strip_transaction_controls(content, "mysql")
        assert result.strip() == "SELECT 1;"

    def test_commit_inside_block_comment_not_stripped(self):
        content = "/* x\nCOMMIT\n*/\nSELECT 1;"
        assert strip_transaction_controls(content, "sqlite") == content

    def test_commit_inside_string_not_stripped(self):
        content = "INSERT INTO t VALUES ('\nCOMMIT\n');"
        assert strip_transaction_controls(content, "sqlite") == content

    def test_case_insensitive(self):
        content = "commit;\nselect 1;"
        result = strip_transaction_controls(content, "sqlite")
        assert result.strip() == "select 1;"

    def test_trailing_inline_comment_not_stripped(self):
        content = "COMMIT -- done\nSELECT 1;"
        assert strip_transaction_controls(content, "sqlite") == content

    def test_semicolon_optional(self):
        content = "COMMIT\nSELECT 1;"
        result = strip_transaction_controls(content, "sqlite")
        assert result.strip() == "SELECT 1;"

    def test_xact_abort_stripped(self):
        content = "SET XACT_ABORT ON;\nSELECT 1;"
        result = strip_transaction_controls(content, "mssql")
        assert result.strip() == "SELECT 1;"

    def test_custom_patterns(self):
        content = "BEGIN TRAN\nSELECT 1;"
        result = strip_transaction_controls(content, "mssql", ["^\\s*BEGIN\\s+TRAN"])
        assert result.strip() == "SELECT 1;"


class TestDetectNonTransactional:
    def test_pg_index_concurrently(self):
        assert detect_non_transactional("postgresql", "CREATE INDEX CONCURRENTLY idx ON t (x);")

    def test_pg_plain_create_table_ok(self):
        assert not detect_non_transactional("postgresql", "CREATE TABLE t (id int);")

    def test_pg_alter_system(self):
        assert detect_non_transactional("postgresql", "ALTER SYSTEM SET work_mem = '64MB';")

    def test_mssql_create_procedure(self):
        assert detect_non_transactional("mssql", "CREATE PROCEDURE p AS SELECT 1;")

    def test_mssql_plain_select_ok(self):
        assert not detect_non_transactional("mssql", "SELECT 1;")

    def test_db2_reorg(self):
        assert detect_non_transactional("db2", "REORG TABLE t;")

    def test_db2_plain_insert_ok(self):
        assert not detect_non_transactional("db2", "INSERT INTO t VALUES (1);")

    def test_oracle_ddl(self):
        assert detect_non_transactional("oracle", "CREATE TABLE t (id number);")

    def test_oracle_dml_ok(self):
        assert not detect_non_transactional("oracle", "INSERT INTO t VALUES (1);")

    def test_string_contains_keyword_not_detected(self):
        assert not detect_non_transactional(
            "postgresql", "INSERT INTO t VALUES ('CREATE DATABASE');"
        )

    def test_matches_inside_comment_not_detected(self):
        assert not detect_non_transactional("postgresql", "/* CREATE DATABASE x */\nSELECT 1;")


class TestProcessFile:
    def test_nowrap_first_line(self):
        result = process_file("-- @nowrap\nCREATE TRIGGER t...", "postgresql", "dev")
        assert not result.wrapped
        assert result.reason == "@nowrap"

    def test_nowrap_mid_file_not_detected(self):
        result = process_file("SELECT 1;\n-- @nowrap", "postgresql", "dev")
        assert result.wrapped

    def test_auto_detect_skip(self):
        result = process_file("CREATE INDEX CONCURRENTLY x ON t (y);", "postgresql", "dev")
        assert not result.wrapped
        assert result.reason == "non-transactional statement detected"

    def test_wrapped_by_default(self):
        result = process_file("CREATE TABLE t (id int);", "postgresql", "dev")
        assert result.wrapped and result.reason is None

    def test_conditionals_applied(self):
        result = process_file(
            "-- @if prod\nSELECT 1;\n-- @endif", "postgresql", "dev"
        )
        assert result.content == ""

    def test_strip_applied_when_enabled(self):
        result = process_file(
            "BEGIN;\nSELECT 1;", "sqlite", "dev", strip=True
        )
        assert result.content.strip() == "SELECT 1;"

    def test_strip_skipped_when_nowrap(self):
        result = process_file(
            "-- @nowrap\nBEGIN;\nSELECT 1;", "sqlite", "dev", strip=True
        )
        assert result.content == "-- @nowrap\nBEGIN;\nSELECT 1;"


class TestWrapContent:
    def test_postgresql(self):
        text = wrap_content("postgresql", "SELECT 1;", "INSERT INTO _migration ...;")
        assert text.startswith("START TRANSACTION;")
        assert "INSERT INTO _migration ...;" in text
        assert text.endswith("COMMIT;")

    def test_mssql_includes_xact_abort(self):
        text = wrap_content("mssql", "SELECT 1;")
        assert text.startswith("SET XACT_ABORT ON;\nBEGIN TRANSACTION;")
        assert text.endswith("COMMIT TRANSACTION;")

    def test_sqlite(self):
        assert wrap_content("sqlite", "SELECT 1;").startswith("BEGIN;")

    def test_oracle_no_begin(self):
        text = wrap_content("oracle", "SELECT 1;", "INSERT INTO _migration ...;")
        assert not text.startswith("BEGIN")
        assert text.endswith("COMMIT;")

    def test_tracker_before_commit(self):
        text = wrap_content("postgresql", "SELECT 1;", "INSERT ...;")
        assert text.index("INSERT ...;") < text.index("COMMIT;")
