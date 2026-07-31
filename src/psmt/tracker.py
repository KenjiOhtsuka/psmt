MIGRATION_DDL = {
    "sqlite": """
CREATE TABLE _migration (
    main_version TEXT NOT NULL,
    sub_version  TEXT NOT NULL,
    applied_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (main_version, sub_version)
);
""".strip(),
    "postgresql": """
CREATE TABLE _migration (
    main_version VARCHAR(255)  NOT NULL,
    sub_version  VARCHAR(255)  NOT NULL,
    applied_at   TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (main_version, sub_version)
);
""".strip(),
    "mysql": """
CREATE TABLE _migration (
    main_version VARCHAR(255) NOT NULL,
    sub_version  VARCHAR(255) NOT NULL,
    applied_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (main_version, sub_version)
) DEFAULT CHARSET=utf8mb4;
""".strip(),
    "mssql": """
CREATE TABLE _migration (
    main_version VARCHAR(255)  NOT NULL,
    sub_version  VARCHAR(255)  NOT NULL,
    applied_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT PK__migration PRIMARY KEY (main_version, sub_version)
);
""".strip(),
    "oracle": """
CREATE TABLE _migration (
    main_version VARCHAR2(255 CHAR) NOT NULL,
    sub_version  VARCHAR2(255 CHAR) NOT NULL,
    applied_at   TIMESTAMP          NOT NULL DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK__migration PRIMARY KEY (main_version, sub_version)
);
""".strip(),
    "db2": """
CREATE TABLE _migration (
    main_version VARCHAR(255) NOT NULL,
    sub_version  VARCHAR(255) NOT NULL,
    applied_at   TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP,
    PRIMARY KEY (main_version, sub_version)
);
""".strip(),
}

NOW_EXPR = {
    "mysql": "CURRENT_TIMESTAMP",
    "postgresql": "CURRENT_TIMESTAMP",
    "mssql": "SYSDATETIME()",
    "oracle": "SYSTIMESTAMP",
    "db2": "CURRENT TIMESTAMP",
    "sqlite": "datetime('now')",
}


def applied_at_literal(engine, utc):
    if engine == "postgresql":
        return f"'{utc}+00'"
    if engine == "oracle":
        return f"TO_TIMESTAMP('{utc}','YYYY-MM-DD HH24:MI:SS')"
    return f"'{utc}'"


def now_expr(engine):
    return NOW_EXPR[engine]


def insert_statement(engine, main_version, sub_version, utc=None):
    literal = now_expr(engine) if utc is None else applied_at_literal(engine, utc)
    return (
        "INSERT INTO _migration (main_version, sub_version, applied_at) "
        f"VALUES ('{main_version}', '{sub_version}', {literal});"
    )


def update_statement(engine, main_version, sub_version, utc):
    literal = applied_at_literal(engine, utc)
    return (
        f"UPDATE _migration SET applied_at = {literal} "
        f"WHERE main_version = '{main_version}' AND sub_version = '{sub_version}';"
    )


def delete_statement(main_version, sub_version):
    return (
        f"DELETE FROM _migration "
        f"WHERE main_version = '{main_version}' AND sub_version = '{sub_version}';"
    )
