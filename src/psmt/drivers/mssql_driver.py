import re

from .. import sqlscan
from ..exceptions import OperationalError
from .base import Driver


class Driver(Driver):
    engine = "mssql"
    extra = "mssql"
    uses_text_wrap = True
    dry_run_handles_unwrapped = True

    def connect(self, cfg, database=None):
        import pyodbc

        if cfg.connection_string:
            conn_str = cfg.connection_string
            if database is not None:
                conn_str = re.sub(r"(?i)Database\s*=\s*[^;]*;", f"Database={database};", conn_str)
            return pyodbc.connect(conn_str, autocommit=False)
        parts = ["DRIVER={ODBC Driver 18 for SQL Server}", f"SERVER={cfg.server},{cfg.port or 1433}"]
        db = database if database is not None else cfg.database
        if db:
            parts.append(f"DATABASE={db}")
        auth = cfg.auth or "password"
        if auth == "azure":
            method = cfg.auth_params.get("method", "ActiveDirectoryIntegrated")
            parts.append(f"Authentication={method}")
            if method == "ActiveDirectoryServicePrincipal":
                self._require_azure_identity()
                client_id = cfg.auth_params.get("client_id")
                client_secret = cfg.auth_params.get("client_secret")
                if client_id:
                    parts.append(f"UID={client_id}")
                if client_secret:
                    parts.append(f"PWD={client_secret}")
                if cfg.auth_params.get("tenant_id"):
                    parts.append(f"TenantID={cfg.auth_params['tenant_id']}")
            elif method in ("ActiveDirectoryPassword", "ActiveDirectoryDefault"):
                if cfg.user:
                    parts.append(f"UID={cfg.user}")
                if method == "ActiveDirectoryPassword" and cfg.password:
                    parts.append(f"PWD={cfg.password}")
        else:
            if cfg.user:
                parts.append(f"UID={cfg.user}")
            if cfg.password:
                parts.append(f"PWD={cfg.password}")
        return pyodbc.connect(";".join(parts) + ";", autocommit=False)

    def _require_azure_identity(self):
        try:
            import azure.identity  # noqa: F401
        except ImportError:
            raise OperationalError('azure-identity not installed; install with: pip install "psmt[mssql]"')

    def execute(self, conn, sql):
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
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
        for stmt in statements:
            try:
                self.execute(conn, "SET NOEXEC ON")
                self.execute(conn, stmt)
                outcomes.append(("ok", ""))
            except Exception as exc:
                outcomes.append(("error", str(exc)))
            finally:
                try:
                    self.execute(conn, "SET NOEXEC OFF")
                except Exception:
                    pass
        return outcomes
