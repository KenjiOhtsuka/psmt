import sqlite3

from .. import sqlscan
from .base import Driver


class Driver(Driver):
    engine = "sqlite"
    uses_text_wrap = True
    dry_run_handles_unwrapped = True

    def connect(self, cfg, database=None):
        path = database if database is not None else (cfg.database or ":memory:")
        conn = sqlite3.connect(path)
        conn.isolation_level = None
        return conn

    def execute(self, conn, sql):
        for stmt in sqlscan.split_statements(sql):
            conn.execute(stmt)

    def query(self, conn, sql):
        cursor = conn.execute(sql)
        return cursor.fetchall()

    def table_exists(self, conn):
        rows = self.query(conn, "SELECT name FROM sqlite_master WHERE type = 'table'")
        return any(str(row[0]) == "_migration" for row in rows)

    def dry_run(self, conn, statements):
        memory = sqlite3.connect(":memory:")
        outcomes = []
        try:
            for stmt in statements:
                try:
                    memory.execute("EXPLAIN " + stmt)
                    outcomes.append(("ok", ""))
                except sqlite3.OperationalError as exc:
                    if "no such table" in str(exc):
                        outcomes.append(("skipped", str(exc)))
                    else:
                        outcomes.append(("error", str(exc)))
        finally:
            memory.close()
        return outcomes
