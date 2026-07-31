# Database Tracking

## `_migration` table

The tool creates and manages a `_migration` table in the target database to track which migrations have been applied.

### Schema

The exact DDL differs per RDBMS. In all cases `main_version` and `sub_version` are **string** columns — `VARCHAR` (or `VARCHAR2`/`TEXT` where that is the engine's natural string type, see the SQLite DDL below) — so they can be used as primary key columns on every engine.

| Column | Meaning | Example |
|---|---|---|
| `main_version` | Folder version | `20260103223344245` |
| `sub_version` | File version | `01` |
| `applied_at` | Timestamp when migration was applied | `2026-01-03 22:33:44` |

SQLite:

```sql
CREATE TABLE _migration (
    main_version TEXT NOT NULL,
    sub_version  TEXT NOT NULL,
    applied_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (main_version, sub_version)
);
```

PostgreSQL:

```sql
CREATE TABLE _migration (
    main_version VARCHAR(255)  NOT NULL,
    sub_version  VARCHAR(255)  NOT NULL,
    applied_at   TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (main_version, sub_version)
);
```

MySQL / MariaDB:

```sql
CREATE TABLE _migration (
    main_version VARCHAR(255) NOT NULL,
    sub_version  VARCHAR(255) NOT NULL,
    applied_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (main_version, sub_version)
) DEFAULT CHARSET=utf8mb4;
```

SQL Server:

```sql
CREATE TABLE _migration (
    main_version VARCHAR(255)  NOT NULL,
    sub_version  VARCHAR(255)  NOT NULL,
    applied_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT PK__migration PRIMARY KEY (main_version, sub_version)
);
```

Oracle:

```sql
CREATE TABLE _migration (
    main_version VARCHAR2(255 CHAR) NOT NULL,
    sub_version  VARCHAR2(255 CHAR) NOT NULL,
    applied_at   TIMESTAMP          NOT NULL DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK__migration PRIMARY KEY (main_version, sub_version)
);
```

DB2 (LUW):

```sql
CREATE TABLE _migration (
    main_version VARCHAR(255) NOT NULL,
    sub_version  VARCHAR(255) NOT NULL,
    applied_at   TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP,
    PRIMARY KEY (main_version, sub_version)
);
```

`VARCHAR(255)` bounds the version columns. `generate` produces version values of at most 17 characters, but a folder/file may be renamed to a longer `main_version` / `sub_version` within the charsets (see [File Structure](02-file-structure.md)); the length is not enforced when reading existing rows, and a version string longer than the column width fails (or, under non-strict MySQL `sql_mode`, silently truncates with a warning) at INSERT time in the database — not at parse time.

MySQL note: with the `utf8mb4` charset declared above (4 bytes/char), a `VARCHAR(255)` column in the composite primary key needs an index-key limit of ≥2040 bytes, which requires a `DYNAMIC`/`COMPRESSED` row format with `innodb_large_prefix` on. These are the defaults from MySQL 5.7.7+ and MariaDB 10.2.2+; on servers where either setting is off (e.g. MySQL 5.6 and 5.7.0–5.7.6), creating this table fails unless the server is configured otherwise.

### Notes

- On first `migrate`, the tool creates the `_migration` table if it does not exist.
- A missing `_migration` table is treated as **empty** (no applied migrations) by `rollback`, `versions`, and `check`; only `migrate` creates it.
- A row is inserted for each `{main_version, sub_version}` pair after a successful migration (a `do` file is applied); when `migrate --force` re-runs an already-recorded version, `applied_at` is **updated** instead. The INSERT/UPDATE runs **inside the same transaction** as the file when the file is wrapped (see [Transaction Wrapping](09-transaction-wrapping.md)).
- Rows are deleted for each `{main_version, sub_version}` pair after a successful rollback (an `undo` file is applied). The DELETE runs inside the same transaction when wrapped.
- `preview` emits INSERT/DELETE statements of the **same shape** (an UPDATE never appears there: `preview` is offline and does not know the `_migration` state, and `--force` is not a preview option) — with `applied_at` rendered as the engine's current-time expression rather than the tool's UTC literal, so manually applied (e.g. DBA-exported) scripts keep `_migration` consistent (see [preview](04-commands.md#migration-bookkeeping-in-the-output)).
- `applied_at` is written by the tool in ISO-8601 format (`YYYY-MM-DD HH:MM:SS`, UTC) and is informational only — never used for ordering. The `DEFAULT` expressions in the DDL are **fallback only**: the tool always supplies `applied_at` in its INSERT. The fallbacks are server/session-local time on MySQL, SQL Server, Oracle, DB2, and PostgreSQL, and UTC on SQLite. The literal is rendered per engine so the session cannot skew or reject it: on PostgreSQL with an explicit `+00` offset (the `DEFAULT CURRENT_TIMESTAMP` fallback alone would record session-local time); on Oracle via `TO_TIMESTAMP('{utc}','YYYY-MM-DD HH24:MI:SS')`, because a bare string literal would be parsed with the session's `NLS_TIMESTAMP_FORMAT` (default `DD-MON-YYYY HH.MI.SSXFF AM`) and fail with `ORA-01861` — the `'YYYY-MM-DD HH:MM:SS'` form only works if that happens to be the session's configured format; on MySQL, SQL Server, DB2, and SQLite the bare `'YYYY-MM-DD HH:MM:SS'` literal is accepted.
- **Orphaned rows** — entries in `_migration` with no matching on-disk folder/file — are never modified by `migrate` / `rollback` / `versions`. They are listed by `versions` as `migrated (only in db)` and flagged by `check` (see [check](04-commands.md#check)); removing them is a manual DBA action.
