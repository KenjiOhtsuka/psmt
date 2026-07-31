from .. import sqlscan
from .base import Driver


class Driver(Driver):
    engine = "postgresql"
    extra = "postgresql"
    uses_text_wrap = True
    dry_run_handles_unwrapped = False

    def connect(self, cfg, database=None):
        import psycopg

        if cfg.connection_string:
            return psycopg.connect(cfg.connection_string)
        kwargs = {
            "host": cfg.server,
            "port": cfg.port or 5432,
        }
        if cfg.user:
            kwargs["user"] = cfg.user
        if cfg.password:
            kwargs["password"] = cfg.password
        kwargs["dbname"] = database or cfg.database or "postgres"
        return psycopg.connect(**kwargs)

    def execute(self, conn, sql):
        for stmt in sqlscan.split_statements(sql):
            conn.execute(stmt)

    def query(self, conn, sql):
        return conn.execute(sql).fetchall()

    def autocommit(self, conn, enabled):
        conn.autocommit = enabled

    def dry_run(self, conn, statements):
        self.execute(conn, "BEGIN")
        outcomes = []
        try:
            for stmt in statements:
                try:
                    self.execute(conn, stmt)
                    outcomes.append(("ok", ""))
                except Exception as exc:
                    outcomes.append(("error", str(exc)))
                    break
        finally:
            self.rollback(conn)
        return outcomes
