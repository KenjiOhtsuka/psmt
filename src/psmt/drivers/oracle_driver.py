from .. import sqlscan
from .base import Driver

_PLAN_TABLE_DDL = """
CREATE TABLE psmt_plan_table (
    statement_id  VARCHAR2(30),
    timestamp     DATE,
    remarks       VARCHAR2(80),
    operation     VARCHAR2(30),
    options       VARCHAR2(255),
    object_node   VARCHAR2(128),
    object_owner  VARCHAR2(30),
    object_name   VARCHAR2(30),
    object_alias  VARCHAR2(65),
    object_instance NUMBER,
    object_type   VARCHAR2(30),
    optimizer     VARCHAR2(255),
    search_columns NUMBER,
    id            NUMBER,
    parent_id     NUMBER,
    depth         NUMBER,
    position      NUMBER,
    cost          NUMBER,
    cardinality   NUMBER,
    bytes         NUMBER,
    other_tag     VARCHAR2(255),
    partition_start VARCHAR2(255),
    partition_stop  VARCHAR2(255),
    partition_id    NUMBER,
    distribution    VARCHAR2(30),
    cpu_cost        NUMBER,
    io_cost         NUMBER,
    temp_space      NUMBER,
    access_predicates VARCHAR2(4000),
    filter_predicates VARCHAR2(4000),
    projection       VARCHAR2(4000),
    time             NUMBER,
    qblock_name      VARCHAR2(30)
)
""".strip()


class Driver(Driver):
    engine = "oracle"
    extra = "oracle"
    uses_text_wrap = False
    dry_run_handles_unwrapped = False

    def connect(self, cfg, database=None):
        import oracledb

        kwargs = {}
        if cfg.user:
            kwargs["user"] = cfg.user
        if cfg.password:
            kwargs["password"] = cfg.password
        dsn = database if database is not None else cfg.database
        if cfg.connection_string:
            dsn = cfg.connection_string
        if dsn:
            kwargs["dsn"] = dsn
        if (cfg.user or "") == "/":
            kwargs["auth_mode"] = oracledb.AUTH_MODE_SYSDBA
        return oracledb.connect(**kwargs)

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
        conn.autocommit = enabled

    def dry_run(self, conn, statements):
        try:
            self.execute(conn, _PLAN_TABLE_DDL)
        except Exception:
            pass
        outcomes = []
        try:
            for stmt in statements:
                try:
                    self.execute(conn, f"EXPLAIN PLAN INTO psmt_plan_table FOR {stmt}")
                    outcomes.append(("ok", ""))
                except Exception as exc:
                    outcomes.append(("error", str(exc)))
        finally:
            self.rollback(conn)
        return outcomes
