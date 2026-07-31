from .. import sqlscan
from ..exceptions import OperationalError
from .base import Driver, NO_DATABASE

_DML_WORDS = {"SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE", "WITH"}


class Driver(Driver):
    engine = "mysql"
    extra = "mysql"
    uses_text_wrap = True
    dry_run_handles_unwrapped = True

    def connect(self, cfg, database=None):
        import pymysql

        if cfg.connection_string:
            raise OperationalError("connection_string is not supported for engine mysql")
        kwargs = {
            "host": cfg.server,
            "port": cfg.port or 3306,
            "charset": cfg.charset or "utf8mb4",
            "autocommit": False,
        }
        if cfg.user:
            kwargs["user"] = cfg.user
        if cfg.password:
            kwargs["password"] = cfg.password
        if database is NO_DATABASE:
            pass
        elif database is not None:
            kwargs["database"] = database
        elif cfg.database:
            kwargs["database"] = cfg.database
        return pymysql.connect(**kwargs)

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

    def autocommit(self, conn, enabled):
        conn.autocommit(enabled)

    def dry_run(self, conn, statements):
        outcomes = []
        for stmt in statements:
            words = sqlscan.first_words(stmt, 1)
            if words and words[0] in _DML_WORDS:
                try:
                    self.execute(conn, "EXPLAIN " + stmt)
                    outcomes.append(("ok", ""))
                except Exception as exc:
                    outcomes.append(("error", str(exc)))
            else:
                outcomes.append(("skipped", "statement type not supported by dry-run"))
        return outcomes
