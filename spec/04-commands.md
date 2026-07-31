# Commands

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Any operational failure: SQL execution error, validation error, config/database not found, DB unreachable, connection failure |
| `2` | Usage error: unknown command, unknown/malformed flag, missing or extra arguments |

`check` has its own status codes — `0` clean, `1` integrity errors, `2` grammar errors (see [check](#check)). Exit `2` is therefore **shared** between grammar errors and usage errors on `check` — distinguish by the message. Usage errors short-circuit before any checking, but the exit code alone does not tell them apart.

## Global flags

| Flag | Description |
|---|---|
| `--verbose` / `-v` | Show `[debug]` messages (repeatable for more detail) |
| `--no-color` | Disable ANSI colors (equivalent to `NO_COLOR` env var) |
| `--help` / `-h` | Show command help |
| `--version`, `-V`, `--tool-version` | Show tool version and exit `0`. On `migrate` / `rollback`, `--version` is taken by version targeting — use `-V` or `--tool-version` there |

`PSMT_VERBOSE` env var is equivalent to `--verbose` (see [Configuration](05-configuration.md)).

**Tool version vs version targeting**: on `migrate` and `rollback` the flag `--version` takes a value (version targeting, see below), so there `-V` / `--tool-version` is the only way to show the tool version. A bare `--version` on `migrate` / `rollback` — no value — is a usage error (exit `2`). On every other command `--version`, `-V`, and `--tool-version` all show the tool version.

## `init`

Scaffold the project structure.

```
psmt init
```

Creates:
- Migration directory (default `./migrations`) if it does not exist.
- `config/` directory if it does not exist, with one file per environment:
  - `config/default.yml`
  - `config/dev.yml`
  - `config/prod.yml`
- Each file contains a `default:` named database config skeleton (`engine: postgresql`, empty connection fields, `migrations_dir` matching `-d`) for the user to fill in (see [Configuration](05-configuration.md)).

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | `./migrations` | Migration directory path |

## `generate`

Create a new migration folder with scaffold files.

```
psmt generate migration <db_key> [--env prod] [--summary "add user table"]
```

- `migration` is a fixed keyword indicating the artifact to generate.
- `<db_key>` is the named database config whose `migrations_dir` is used (see [Databases and commands](05-configuration.md#databases-and-commands)).

Prompt:

1. **Summary** — short description of the change. Spaces are replaced with `_`.

Creates:
- Folder: `{timestamp}_{summary}`
- `01_migrate__do.sql` — empty do migration scaffold
- `01_migrate__undo.sql` — empty undo migration scaffold

Spaces in summary are replaced with `_`. Example: `"add user table"` becomes `add_user_table`.

The timestamp is generated at the moment of invocation and rendered as 17 digits, UTC: `%Y%m%d%H%M%S` (14 digits) plus a 3-digit milliseconds field — e.g. `20260103223344245`. The generated `main_version` is **digits only**, but a folder may be renamed to any `main_version` in the charset `[A-Za-z0-9-]` (letters, digits, hyphens — see [File Structure](02-file-structure.md)); the exact generated format is part of the public contract only in that it yields a valid `main_version`. Two folders differing only in the timestamp's trailing digit are distinct versions. The scaffolded `sub_version` is `01` (digits only) and may likewise be renamed within `[A-Za-z0-9-]`.

The migrations directory is resolved from the named config `<db_key>` in the selected environment's config file; `-d` overrides it.

**Input sanitization**: the summary is restricted to the safe character set — letters, digits, `-`, `_`, `.`. All other characters are replaced with `_`. Path separators (`/`, `\`) and `..` sequences are also replaced with `_` to prevent path traversal outside the migrations directory. If the sanitized summary is **empty** (e.g. `--summary ""` or `--summary "///"`), `generate` fails with a usage error (exit `2`): `[error] invalid summary: {summary}` — an empty description would produce a non-conforming `{timestamp}_` folder that all commands ignore.

**Timestamp collision**: the timestamp has millisecond precision. If the resulting folder name already exists **or a folder with the same `main_version` already exists** (under a different name), the tool retries with a **fresh timestamp** until the folder name is unique and no folder shares the `main_version`. There is **no `_2` / `_3` suffix scheme**: appending a suffix after the first underscore would change the *description*, not the `main_version`, and would recreate the duplicate-`main_version` condition the retry exists to avoid. Because the timestamp has millisecond precision, a second retry is practically never needed.

**Non-interactive input**: if `--summary` is not given and stdin is not a TTY, `generate` fails with `[error] interactive input unavailable; pass --summary` and exits `1`.

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | named config's `migrations_dir` | Migration directory (overrides config) |
| `-e, --env` | `default` | Environment (selects the config file) |
| `--summary` | — | Summary text (skip prompt) |

## `migrate`

Apply pending migrations. Supports targeting specific versions and environment-based conditional SQL.

```
psmt migrate
```

- Iterates over folders sorted by `main_version` **string** ascending.
- Within each folder, iterates over files sorted by `sub_version` **string** ascending.
- Executes every `*__do.sql` file that is not already recorded in `_migration`.
- Only files matching the naming pattern are processed; non-conforming `.sql` files are ignored (and non-`.sql` files like `README.md` are silently ignored by every command) — `check` is the command that flags the former (see [check](#check)).
- Inserts a `_migration` row after each successful execution.
- Stops on first error; does not roll back previously applied files in the same run.
- Processes `-- @if` / `-- @else` / `-- @endif` directives against the active environment (see [Conditional SQL](08-conditional-syntax.md)).

### Version targeting

| Value | Behavior |
|---|---|
| `--version {main}` | Migrate all **pending** files under the given main version folder (files already recorded in `_migration` are skipped; with `--force`, all files are re-run) |
| `--version {main}:{sub}` | Migrate a single file |
| `--version {v1},{v2}` | Migrate multiple versions (comma-separated; each element may be `{main}` or `{main}:{sub}` in any mix) |

A value without `:` is always interpreted as `{main}` (a folder name). There is **no bare `{sub}` form** — a `sub_version` only targets within its folder, so it must always be written `{main}:{sub}`.

**Validation**: `main` and `sub` must each match the charset `[A-Za-z0-9-]` (letters, digits, hyphens). Anything else is rejected to prevent path traversal when resolving file paths. `{sub}` must **exactly** equal the on-disk `sub_version` string — no normalization is applied, so `--version 20260103223344245:1` does **not** match `01` (use `20260103223344245:01`).

**Usage errors (exit `2`)**: malformed `--version` values (characters outside `[A-Za-z0-9-]`, empty parts, a bare `--version` with no value), a malformed or non-integer `--steps` value, `--steps 0` or a negative `--steps`, and the `--version` + `--steps` combination are all usage errors — the tool exits `2` before touching the database.

**Not found (exit `1`)**: a well-formed `--version` that matches no folder/file on disk is an operational error — `[error] migration version not found: {version}`, exit `1`. For a comma-separated list the message echoes the offending element (`[error] migration version not found: {v}`); the run stops at the first missing element, after earlier elements have been applied normally (stop-on-first-error).

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | named config's `migrations_dir` | Migration directory (overrides config) |
| `-e, --env` | `default` | Active environment (selects database config and migrations dir) |
| `--db` | `default` | Named database configuration (see [Databases and commands](05-configuration.md#databases-and-commands)) |
| `--version` | all | Specific version(s) to migrate. `all` is a **reserved token** only when it is the **entire** `--version` value — it is never interpreted as a folder name then; it simply means "no specific version" (the default). Within a `{main}:{sub}` pair or a comma-list element, `all` is an ordinary version part (`--version all:01` targets folder `all`, sub `01`; `--version 2026:all` targets sub `all`). Consequence: a folder literally named `all` cannot be selected as a whole via `--version all` (use `--version all:{sub}` per file, or rename the folder) |
| `--dry-run` | `false` | Connect to DB and validate SQL without applying (see [Dry-run](#dry-run)) |
| `--steps` | all | Limit to the first N **pending** migrations in migration order (ascending). Accepts a positive integer or `all`; `0` and negative values are usage errors (exit `2`) |
| `--force` | `false` | Execute even if already recorded in `_migration` (see [Force](#force)) |

If both `--version` and `--steps` are given, the tool raises an error with an explanatory message. An explicit `--version all` counts as "given" for this rule (it is still a `--version` argument), so `--version all --steps N` is a usage error (exit `2`) — use `--steps` alone.

## `rollback`

Revert applied migrations using undo files. Supports version targeting and environment-based conditional SQL.

```
psmt rollback
```

- Iterates over applied migrations in reverse order — `main_version` string-descending, then `sub_version` string-descending.
- Executes the matching `*__undo.sql` file for each applied migration.
- Deletes the `_migration` row after each successful execution.
- Stops on first error.
- Processes `-- @if` / `-- @else` / `-- @endif` directives against the active environment.

### Version targeting

Same as `migrate` — see [migrate version targeting](#version-targeting).

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | named config's `migrations_dir` | Migration directory (overrides config) |
| `-e, --env` | `default` | Active environment (selects database config and migrations dir) |
| `--db` | `default` | Named database configuration (see [Databases and commands](05-configuration.md#databases-and-commands)) |
| `--version` | all | Specific version(s) to roll back |
| `--dry-run` | `false` | Connect to DB and validate SQL without applying (see [Dry-run](#dry-run)) |
| `--steps` | `1` | Number of applied migrations at the top of rollback order (string-descending) to roll back; `all` rolls back everything |
| `--force` | `false` | Execute even if not recorded in `_migration` (see [Force](#force)) |

If both `--version` and `--steps` are given, the tool raises an error with an explanatory message. An explicit `--version all` counts as "given" for this rule (it is still a `--version` argument), so `--version all --steps N` is a usage error (exit `2`) — use `--steps` alone.

The default differs deliberately: `migrate` defaults to `all` (apply everything pending), `rollback` defaults to `1` (undo one migration at a time, as a safety default).

## `check`

Validate migration file integrity and SQL grammar without executing.

```
psmt check
```

- File integrity checks (offline, no DB connection):
  - Folder names match `{main_version}_{description}` pattern.
  - File names match `{sub_version}_{description}__{direction}.sql` pattern.
  - No two files in the same folder share the same `{sub_version}` **and the same direction** — a do file and its matching undo file legitimately share the pair, so duplicates are only flagged within one direction (e.g. two `01_...__do.sql` files in the same folder).
  - No duplicate `main_version` across folders (fatal).
  - Every do file has a matching undo file and vice versa (warns, not fatal).
  - Conditional directives (`-- @if` / `-- @else` / `-- @endif`) are balanced and well-formed.
- Grammar check (requires DB connection):
  - Uses RDBMS-specific validation (see [Dry-run](#dry-run)).
  - Non-transactional statement auto-detection is verified.
  - Orphaned `_migration` rows (recorded but no matching on-disk file) — warns, not fatal.

Exit code:
- `0` — no errors.
- `1` — integrity errors found. Grammar check is **skipped** (the file set is unreliable).
- `2` — integrity OK, but grammar errors found.

**Warnings do not affect the exit code** — only errors do. `0` is returned when there are warnings but no errors.

Exit `1` is shared with operational failures (config or migrations directory missing, database unreachable during the grammar phase). These are **not** an integrity verdict: `check` exits `1` for them too, but the message is an `[error]` rather than an integrity-error report. An integrity verdict is only reached when the tool was able to run at least the integrity phase to completion. If an operational failure occurs before or during a phase, no verdict is implied — the exit code merely reflects "not successful".

Output: findings are printed as individual prefixed lines using the standard [message levels](07-logging.md#message-levels) — one `[error]` (or `[warn]`) per finding, `[error] {folder}/{file}: {reason}` for integrity findings, with a summary line at the end. `check` does **not** use the prefix-less `versions`-style table output.

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | named config's `migrations_dir` | Migration directory (overrides config) |
| `-e, --env` | `default` | Environment (selects database config and migrations dir) |
| `--db` | `default` | Named database configuration to check against (see [Databases and commands](05-configuration.md#databases-and-commands)) |
| `--no-grammar` | `false` | Skip the DB-connected grammar check |
| `--no-db` | `false` | Alias for `--no-grammar` |

## `preview`

Preview the exact SQL that `migrate` / `rollback` would execute — after conditional processing and transaction wrapping — **including the `_migration` bookkeeping statement**, without executing it.

```
psmt preview {main}:{sub} [--undo] [--env dev]
```

- Version `{main}:{sub}` is **required** — previewing every file at once is not useful. A missing positional, or a value without `:`, is a usage error (exit `2`). A well-formed version that matches no folder/file on disk (or a folder with no matching direction file) is an operational error: `[error] migration version not found: {version}`, exit `1`.
- Defaults to the `do` file; `--undo` selects the undo file instead.
- Applies the same processing as execution:
  - `-- @if` / `-- @else` / `-- @endif` conditionals
  - transaction wrapping — unless `-- @nowrap` is present or a non-transactional statement is auto-detected (see [Transaction Wrapping](09-transaction-wrapping.md))
- Prints the resulting SQL to stdout.
- `preview` is **fully offline** — it never connects to the database.

### `_migration` bookkeeping in the output

The output is a complete, self-contained script for the target engine: the file's SQL **plus** the tracking statement the tool would execute — the same INSERT/DELETE **shape**, with `applied_at` rendered as the engine's current-time expression rather than the UTC literal the tool itself writes (see [Database Tracking](03-database-tracking.md)), because the apply moment is unknown at preview time. The result can be handed to a DBA or imported into a change-management tool without desynchronizing `_migration`:

- `do` file → `INSERT INTO _migration (main_version, sub_version, applied_at) VALUES ('{main}', '{sub}', {now})` where `{now}` is the engine's current-time expression: MySQL `CURRENT_TIMESTAMP`, PostgreSQL `CURRENT_TIMESTAMP` (the `timestamptz` column records the instant; `AT TIME ZONE 'UTC'` is **not** used here because it would yield `timestamp without time zone` and be re-interpreted in the session timezone on insert), SQL Server `SYSDATETIME()`, Oracle `SYSTIMESTAMP`, DB2 `CURRENT TIMESTAMP`, SQLite `datetime('now')`. The recorded value remains informational only (never used for ordering, see [Database Tracking](03-database-tracking.md)).
- `undo` file → `DELETE FROM _migration WHERE main_version = '{main}' AND sub_version = '{sub}'`.
- When the file is transaction-wrapped, the tracking statement is emitted **inside** the same transaction block (before `COMMIT`), matching the tool's execution — a failed manual run rolls back both. When the file is not wrapped (`-- @nowrap` / auto-detected), the tracking statement is emitted after the file content, separated by a comment line.
- `--no-tracker` omits the tracking statement (e.g. when the consuming tool tracks migrations itself).
- `--raw` prints the file content as-is and **never** includes the tracking statement.
- The tracking statements assume `_migration` exists. For a database with no `_migration` table yet, create it from the per-engine DDL in [Database Tracking](03-database-tracking.md) before applying the first exported script.

### Output to file

`--output DIR` writes the preview to a file instead of stdout. The value is **required** — a bare `--output` is a usage error (exit `2`); use `--output .` for the current directory:

```
{dir or ./}/{env}/{folder_name}/{file_name}
```

Example with `--output build`:

```
build/dev/20260103223344245_add_users_table/01_create_users__do.sql
```

When the value is `.`, the base is the current directory.

In file mode, the tool prints `[info] wrote {n} file(s) to {dir}`.

The written files include the `_migration` bookkeeping statement (unless `--no-tracker` or `--raw`), making each file directly runnable — e.g. for a production database that forbids programmatic command execution, where a DBA applies the exported files manually.

**Path safety**: when writing files, any `.` or `/` characters in the environment name are replaced with `_` before it is used as a path component (e.g. `--env default.qa` writes to `default_qa/`). This prevents path traversal; the sanitized value is used for the output path only — config file resolution still uses the raw environment name (`config/default.qa.yml`). Note that `/` cannot occur in a valid environment name at all (see [Configuration](05-configuration.md)); the sanitization is defensive. The example `default.qa` shows the relevant case.

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | named config's `migrations_dir` | Migration directory (overrides config) |
| `-e, --env` | `default` | Active environment (selects config file and conditional SQL) |
| `--db` | `default` | Named database configuration (see [Databases and commands](05-configuration.md#databases-and-commands)) |
| `--undo` | `false` | Preview the undo file instead of do |
| `--no-tracker` | `false` | Omit the `_migration` bookkeeping statement from the output |
| `--output` | `.` (current directory) | Directory to write the preview to (file mode); value required |
| `--raw` | `false` | Print file content as-is, skip conditional, wrap, and tracking-statement processing |

## `versions`

Show the status of all migrations — which have been applied and which are pending.

```
psmt versions
```

- Scans the migrations directory for all folders and `_migration` table to produce a combined view.
- Only files matching the naming pattern are included; non-conforming files are ignored.
- Three possible statuses:
  - **migrated** — folder+file exist on disk and recorded in DB.
  - **migrated (only in db)** — entry in `_migration` but no matching folder/file on disk (orphaned).
  - **not migrated (only in file)** — folder+file on disk but no matching DB entry (pending).

The same statuses appear in the [overview](01-overview.md) as **migrated** / **pending** / **orphaned**: migrated = applied, pending = not migrated (only in file), orphaned = migrated (only in db).

### Output format

```
{main_version}:{sub_version}  {status}
```

One line per entry, sorted by `main_version` then `sub_version` (both **string** ascending). Entries on disk and in DB are merged into a single sorted list.

The separator is a colon — `:` appears in neither charset — so the line is unambiguous even though both `main_version` and `sub_version` may themselves contain hyphens (e.g. `2026-alpha-01:beta-2` = main `2026-alpha-01`, sub `beta-2`). This mirrors the `--version {main}:{sub}` targeting syntax.

### Output example

```
20260103223344245:01  migrated
20260103223344245:02  migrated
20260105120000000:01  migrated
20260105120000000:03  migrated (only in db)
20260107151515000:01  not migrated (only in file)
```

The example shows a hypothetical database state independent of the [file-structure example](02-file-structure.md): `20260105120000000:03` exists only in the database (an orphaned row, no matching file on disk), while `20260107151515000:01` exists only on disk (pending).

### Flags

| Flag | Default | Description |
|---|---|---|
| `-d, --dir` | named config's `migrations_dir` | Migration directory (overrides config) |
| `-e, --env` | `default` | Environment name used to resolve database config |
| `--db` | `default` | Named database configuration (see [Databases and commands](05-configuration.md#databases-and-commands)) |

## `db create`

Create the target database.

```
psmt db create [db]
```

- `[db]` is the named database config (default: `default`).
- Connects to the database server (not the target database) and runs `CREATE DATABASE`.
- Connection details for the server come from config, **minus the database name**: the `database` field is the database to create (not the connection target). With a full `connection_string`, the `Database=` part is stripped for the server-level connection.
- Server-level connection fallback database:
  - PostgreSQL: connects to `postgres`.
  - SQL Server: connects to `master`.
  - DB2 (LUW): connects to `SAMPLE` if present, otherwise any configured instance (the target database does not yet exist).
  - MySQL / SQLite: no fallback database is required.
  - Oracle: there is no `CREATE DATABASE` — a database is an existing instance (SID/service). `db create` for Oracle connects **as `/` (SYSDBA)** and creates a **schema** instead: `CREATE USER {database} IDENTIFIED BY {password}` + `GRANT CONNECT, RESOURCE TO {database}`. No `DEFAULT TABLESPACE` clause is emitted, so the instance's default tablespace is used (hard-coding `users` would fail with ORA-00959 on instances without a `USERS` tablespace). The tool also issues `ALTER USER {database} QUOTA UNLIMITED ON {default_tablespace}`, reading the instance's default tablespace as SYSDBA (from `DATABASE_PROPERTIES` / `DBA_USERS`) — since Oracle 12.1 the `RESOURCE` role no longer grants `UNLIMITED TABLESPACE`, and without a quota the schema's first `CREATE TABLE` fails with `ORA-01950`. `db create` / `db destroy` on Oracle therefore require `user` = `/` (SYSDBA), `password`, and a writable default tablespace.
- For sqlite, `db create` creates an empty file at the `database` path — there is no server connection.
- `CREATE DATABASE` applies the configured `charset` where the engine supports it: MySQL `CHARACTER SET {charset}` (default `utf8mb4`), PostgreSQL `ENCODING '{charset}'` (default `UTF8`), DB2 `USING CODESET {charset}` (default `UTF8`). Oracle's charset is fixed by the instance; the configured `charset` (default `AL32UTF8`) is informational only. See [Charset](05-configuration.md#charset).
- Connects through the engine's Python driver, in-process (see [Connection modes](05-configuration.md#connection-modes)).

### Flags

| Flag | Default | Description |
|---|---|---|
| `-e, --env` | `default` | Environment (selects the config file) |

## `db destroy`

Drop the target database.

```
psmt db destroy [db] --force
```

- `[db]` is the named database config (default: `default`).
- Connects to the database server and runs `DROP DATABASE`.
- Requires `--force` to proceed.
- This is irreversible.
- For sqlite, `db destroy --force` deletes the file at the `database` path, including any WAL/SHM sidecar files (`-wal`, `-shm`) if present. All open connections to the file must be closed first; the three files are removed together so a stale WAL is not left behind for a future file at the same path.
- PostgreSQL `DROP DATABASE` cannot run inside a transaction — the server-level connection runs in autocommit. PostgreSQL and SQL Server both fail if any other session is connected to the target database; on SQL Server `DROP DATABASE` also fails if the target database is the connection's current database (hence the `master` fallback).
- For Oracle, `db destroy --force` drops the **schema** created by `db create`: `DROP USER {database} CASCADE` (SYSDBA connection). DB2 uses `DROP DATABASE {database}` (autocommit; no active connections to the target).
- Connects through the engine's Python driver, in-process.
- Same server-level connection handling as `db create`.

### Flags

| Flag | Default | Description |
|---|---|---|
| `-e, --env` | `default` | Environment (selects the config file) |
| `--force` | `false` | Required to destroy the database; without it the command exits `2` (usage error — required flag missing) |

## Dry-run

`--dry-run` on `migrate` / `rollback` connects to the database and validates the SQL **without applying** any change.

Per-RDBMS validation method:

| RDBMS | Method |
|---|---|
| SQL Server | `SET NOEXEC ON` per statement batch (compiles without executing) |
| PostgreSQL | `BEGIN` … `ROLLBACK` wrapper, or `EXPLAIN` per statement |
| MySQL | `EXPLAIN` per DML statement |
| SQLite | `EXPLAIN` per statement on an in-memory connection |
| Oracle | `EXPLAIN PLAN [INTO psmt_plan_table] FOR` per DML statement, then `ROLLBACK`; the plan table is created if missing (see limitations) |
| DB2 (LUW) | Execute with autocommit off, then `ROLLBACK` (DB2 has no `START TRANSACTION`; the transaction is an implicit unit of work) |

- The `_migration` table is **not** modified during dry-run.
- Conditional processing still applies (only the active environment's SQL is validated).
- If a statement that **can** be validated fails validation, the error is printed and the run reports failure.
- Statements the chosen method **cannot** validate are never executed and are skipped with `[warn] dry-run not validated (statement type not supported by dry-run)`; they do **not** trigger the failure rule. This covers MySQL DDL (plain `EXPLAIN` cannot plan `CREATE TABLE`) and SQLite statements that fail compilation with `no such table` against the empty in-memory schema (see limitations). A run with only such skipped statements still succeeds for the statements it did validate.
- **No statement that could commit changes is ever executed during dry-run.** Files that cannot be transactionally wrapped (`-- @nowrap`, or auto-detected non-transactional statements) are therefore handled per RDBMS:
  - **PostgreSQL**: skipped with `[warn] dry-run skipped (non-transactional statement)` and counted in the summary. They are *not* executed as-is — that would really apply the change (e.g. build a `CREATE INDEX CONCURRENTLY`).
  - **Oracle**: any DDL file is skipped with the same warning — Oracle DDL commits implicitly, so executing it during dry-run would be a real change. DML files are validated via `EXPLAIN PLAN FOR`.
  - **DB2**: auto-detected non-transactional statements (`REORG`, `RUNSTATS`, `CREATE DATABASE` / `DROP DATABASE`) are skipped with the warning; everything else is validated by executing in an implicit unit of work with autocommit off, then `ROLLBACK` (DB2 LUW DDL is transactional, so this validates it fully).
  - **SQL Server / MySQL / SQLite**: never executed either — SQL Server via `SET NOEXEC ON`, MySQL/SQLite via `EXPLAIN` — so the safety promise holds even when the file cannot be wrapped; validation *quality* caveats are in the limitations below.
- PostgreSQL `EXPLAIN` does not meaningfully validate utility statements (it reports the statement rather than planning an execution); the non-transactional utility statements listed in [Transaction Wrapping](09-transaction-wrapping.md) are covered by the skip rule above.

**Limitations**:
- MySQL `EXPLAIN` only plans DML statements (SELECT/INSERT/UPDATE/DELETE) and does **not** validate DDL like `CREATE TABLE`; MySQL DDL dry-run is best-effort. Never use `EXPLAIN ANALYZE` — it executes the statement. Plain `EXPLAIN` of DML requires MySQL 5.6.3+ (MariaDB 10.0+).
- SQLite `EXPLAIN` compiles any statement (including DDL) to VDBE opcodes, so it does validate DDL — but against an **empty** in-memory schema. Statements that reference objects created by earlier migrations (`ALTER TABLE x ...`, `CREATE INDEX ... ON x ...`) fail with `no such table` even for valid migrations. Because the empty schema cannot distinguish a genuinely missing object from an object an earlier migration would have created, the tool **downgrades `no such table` errors on SQLite** to the `[warn] dry-run not validated (...)` skip rather than a validation failure; only self-contained statements (e.g. `CREATE TABLE`, `INSERT ... VALUES`) are truly validated, and any other error class (e.g. a syntax error) remains a real failure.
- Oracle `EXPLAIN PLAN FOR` writes to a plan table. The default `PLAN_TABLE` is absent on a stock instance (`ORA-00942`) until `utlxplan.sql` is run, so the tool targets a dedicated table and creates it if missing (`CREATE TABLE psmt_plan_table (...)`), issuing `EXPLAIN PLAN INTO psmt_plan_table FOR ...` — a stock instance then works without setup.
- SQL Server `SET NOEXEC ON` compiles without executing. It uses **deferred name resolution**: objects referenced but created earlier in the same file are *not* flagged (DDL is never materialized), so cross-statement references are silently **not validated** — a false-negative, not a false failure. Syntax errors and references to existing objects still surface (e.g. Msg 207). Each statement must be in its own batch (the tool sends them as separate batches), because `NOEXEC` cannot be set in the same batch as the statement it controls. `SET SHOWPLAN_TEXT ON` is **not** used: it and `SET NOEXEC ON` cannot share a batch (Msg 1067), and SHOWPLAN additionally changes result shapes.
- For RDBMS where DDL dry-run is best-effort, `check` with a live connection is more reliable for grammar validation.
- On PostgreSQL, `BEGIN`…`ROLLBACK` dry-run is *not* side-effect free: sequence values consumed by `nextval` are not restored, and locks are held until the rollback. The same applies to DB2's execute-then-`ROLLBACK` dry-run — DB2 sequence `NEXTVAL` / identity values consumed during validation are not restored by the rollback, and locks are held until it completes. The `[warn]`-skipped files are the only ones guaranteed to touch nothing.

For SQLite, dry-run uses an in-memory connection (`:memory:`) so the target database file is never opened or modified — this works even if the file does not exist yet.

## Force

`--force` bypasses the migration status check in `_migration`.

- `migrate --force {version}` executes the do file even if it is already recorded (re-runs SQL, then updates `applied_at`).
- `rollback --force {version}`: executes that version's undo file even if it is **not** recorded in `_migration`. If a row exists it is deleted; if none exists, nothing is inserted.
- Without a `--version` target, `--force` has **no effect**: migration/rollback selection is driven purely by `_migration` state, so there is nothing to force. `migrate --force` and `rollback --force` behave exactly like their non-`--force` counterparts.
- `--force` does **not** bypass validation or wrapping rules.
- Without `--force`:
  - `migrate` on an already-migrated version prints `[info] already migrated` and skips.
  - `rollback` on a not-applied version prints `[info] not migrated` and skips.
