from .. import sqlscan
from .base import Driver


class Driver(Driver):
    engine = "db2"
    extra = "db2"
    uses_text_wrap = False
    dry_run_handles_unwrapped = False

    def connect(self, cfg, database=None):
        import ibm_db_dbi

        db = database if database is not None else cfg.database
        parts = []
        if db:
            parts.append(f"DATABASE={db}")
        parts.append(f"HOSTNAME={cfg.server}")
        parts.append(f"PORT={cfg.port or 50000}")
        parts.append("PROTOCOL=TCPIP")
        if cfg.user:
            parts.append(f"UID={cfg.user}")
        if cfg.password:
            parts.append(f"PWD={cfg.password}")
        conn = ibm_db_dbi.connect(";".join(parts) + ";", "", "")
        conn.autocommit = False
        return conn

    def execute(self, conn, sql):
        cursor = conn.cursor()
        try:
            for stmt in sqlscan.split_statements(sql):
                cursor.execute(stmt)
        finally:
            cursor.close()

    def query(self, conn, sql):
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            return cursor.fetchall()
        finally:
            cursor.close()

    def dry_run(self, conn, statements):
        outcomes = []
        try:
            for stmt in statements:
                try:
                    self.execute(conn, stmt)
                    outcomes.append(("ok", ""))
                except Exception as exc:
                    outcomes.append(("error", str(exc)))
        finally:
            self.rollback(conn)
        return outcomes
