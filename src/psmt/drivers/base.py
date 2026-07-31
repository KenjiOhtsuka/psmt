from .. import tracker


class Driver:
    engine = None
    extra = None
    uses_text_wrap = True
    dry_run_handles_unwrapped = False

    def connect(self, cfg, database=None):
        raise NotImplementedError

    def server_connect(self, cfg):
        return self.connect(cfg, database=_SERVER_FALLBACK[self.engine])

    def execute(self, conn, sql):
        raise NotImplementedError

    def query(self, conn, sql):
        raise NotImplementedError

    def commit(self, conn):
        conn.commit()

    def rollback(self, conn):
        conn.rollback()

    def close(self, conn):
        conn.close()

    def autocommit(self, conn, enabled):
        conn.autocommit = enabled

    def table_exists(self, conn):
        sql = _TABLE_EXISTS_SQL[self.engine]
        return any(str(row[0]) == "_migration" for row in self.query(conn, sql))

    def ensure_migration_table(self, conn):
        if not self.table_exists(conn):
            self.execute(conn, tracker.MIGRATION_DDL[self.engine])
            self.commit(conn)

    def fetch_applied(self, conn):
        if not self.table_exists(conn):
            return set()
        return {
            (str(row[0]), str(row[1]))
            for row in self.query(conn, "SELECT main_version, sub_version FROM _migration")
        }

    def dry_run(self, conn, statements):
        raise NotImplementedError


_TABLE_EXISTS_SQL = {
    "sqlite": "SELECT name FROM sqlite_master WHERE type = 'table'",
    "postgresql": "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()",
    "mysql": "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()",
    "mssql": "SELECT name FROM sys.tables",
    "oracle": "SELECT table_name FROM user_tables",
    "db2": "SELECT tabname FROM syscat.tables WHERE tabschema = CURRENT SCHEMA",
}

_SERVER_FALLBACK = {
    "postgresql": "postgres",
    "mysql": None,
    "sqlite": None,
    "mssql": "master",
    "oracle": None,
    "db2": "SAMPLE",
}
