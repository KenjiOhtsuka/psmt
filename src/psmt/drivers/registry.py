from ..exceptions import DriverNotInstalledError, OperationalError

_DRIVERS = {
    "sqlite": ("psmt.drivers.sqlite_driver", None),
    "postgresql": ("psmt.drivers.postgres_driver", "psycopg"),
    "mysql": ("psmt.drivers.mysql_driver", "pymysql"),
    "mssql": ("psmt.drivers.mssql_driver", "pyodbc"),
    "oracle": ("psmt.drivers.oracle_driver", "oracledb"),
    "db2": ("psmt.drivers.db2_driver", "ibm_db"),
}

_EXTRAS = {
    "postgresql": "postgresql",
    "mysql": "mysql",
    "mssql": "mssql",
    "oracle": "oracle",
    "db2": "db2",
}


def get_driver(engine):
    entry = _DRIVERS.get(engine)
    if entry is None:
        raise OperationalError(f"unknown engine: {engine}")
    module_name, library = entry
    if library is not None:
        try:
            __import__(library)
        except ImportError:
            raise DriverNotInstalledError(
                f'driver not installed for engine {engine}; install with: pip install "psmt[{_EXTRAS[engine]}]"'
            )
    from importlib import import_module

    module = import_module(module_name)
    return module.Driver()
