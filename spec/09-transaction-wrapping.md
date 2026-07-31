# Transaction Wrapping

## Default behavior

By default, every SQL file is wrapped in a transaction before execution:

```sql
SET XACT_ABORT ON;
BEGIN TRANSACTION;

-- original file content

COMMIT TRANSACTION;
```

- `SET XACT_ABORT ON` is added only for T-SQL (SQL Server). For other RDBMS it is omitted.
- The wrapping adapts to the target RDBMS:
  - `START TRANSACTION` for MySQL, PostgreSQL.
  - `BEGIN TRANSACTION` for SQL Server.
  - `BEGIN` for SQLite.
  - **Oracle and DB2 (LUW): no explicit `BEGIN`** — both start a transaction implicitly. Oracle and DB2 have **no** `START TRANSACTION` statement (on DB2 it is a syntax error, SQL0104); a transaction begins as an implicit unit of work with the first statement. The driver switches off autocommit and issues only `COMMIT` / `ROLLBACK`.
- Transaction control is driver-managed: `BEGIN` → execute statements → **`ROLLBACK` on any error** → `COMMIT` on success. For wrapped files the tool executes the `_migration` bookkeeping statement (**INSERT** for `migrate` — an **UPDATE** of `applied_at` when `--force` re-runs an already-recorded version — **DELETE** for `rollback`, see [Database Tracking](03-database-tracking.md)) **inside the same transaction, before `COMMIT`** — a failed run rolls back both the migration and its tracking row. This guarantees atomicity **where the RDBMS supports transactional DDL**: PostgreSQL, SQLite, SQL Server (SQL Server DDL is transactional — `SET XACT_ABORT ON` makes runtime errors abort the whole transaction), and DB2 (LUW DDL is transactional). MySQL and Oracle implicitly commit on DDL statements, so a failed file can leave partial changes even with wrapping; `SET XACT_ABORT ON` is an extra safety net for SQL Server only.

### RDBMS error behavior

| RDBMS | Behavior on statement error | Why the driver must roll back explicitly |
|---|---|---|
| SQL Server | `XACT_ABORT` off by default — transaction stays open | Error does not auto-abort; without `SET XACT_ABORT ON`, partial changes can be committed |
| PostgreSQL | Transaction enters aborted state | Subsequent statements fail; still requires explicit `ROLLBACK` |
| MySQL | Transaction stays open | Error does not abort it; later statements can still succeed, so partial changes need explicit `ROLLBACK` |
| SQLite | Failed statement is rolled back; transaction stays open | Later statements can still succeed, so partial changes need explicit `ROLLBACK` |
| Oracle | Transaction stays open | Error does not abort it; partial changes need explicit `ROLLBACK` (DDL already committed implicitly) |
| DB2 | Failed statement is rolled back (statement-level rollback); the unit of work stays open | Error does not abort the unit of work; later statements can still succeed, so partial changes need explicit `ROLLBACK` (only deadlock/timeout, SQL0911/SQLSTATE 40001, rolls back the whole unit of work) |

## `-- @nowrap`

If a SQL file contains `-- @nowrap` on the **first line**, transaction wrapping is **skipped** — the file is executed as-is.

```
-- @nowrap
CREATE TRIGGER ...
```

The directive is expected at the **first line** of the file. Implementation may also scan the full file.

Use `-- @nowrap` when:
- The RDBMS does not support nested transactions or DDL inside transactions.
- The SQL file contains its own transaction control (`BEGIN TRAN`, `COMMIT`, `ROLLBACK`).
- The migration performs operations that must run outside a transaction.

## Auto-detection of non-transactional statements

Even without `-- @nowrap`, the tool **auto-detects** statements that cannot run inside a transaction, or that cannot run inside the tool's single-batch wrapper. If any of the following are found in the SQL content, wrapping is automatically skipped:

| Statement | RDBMS | Reason |
|---|---|---|
| `CREATE DATABASE` / `ALTER DATABASE` / `DROP DATABASE` | SQL Server | Cannot run in an explicit transaction |
| `CREATE FULLTEXT INDEX` / `ALTER FULLTEXT INDEX` / `DROP FULLTEXT INDEX` | SQL Server | Cannot run in an explicit transaction |
| `CREATE FULLTEXT CATALOG` / `ALTER FULLTEXT CATALOG` / `DROP FULLTEXT CATALOG` | SQL Server | Cannot run in an explicit transaction |
| `RECONFIGURE` | SQL Server | Cannot run in an explicit transaction |
| `CREATE TRIGGER` / `ALTER TRIGGER` | SQL Server | Must be the first statement in a batch — conflicts with the single-batch wrapper |
| `CREATE VIEW` / `ALTER VIEW` | SQL Server | Must be the first statement in a batch |
| `CREATE FUNCTION` / `ALTER FUNCTION` | SQL Server | Must be the first statement in a batch |
| `CREATE PROCEDURE` / `ALTER PROCEDURE` | SQL Server | Must be the first statement in a batch |
| `CREATE INDEX CONCURRENTLY` / `CREATE UNIQUE INDEX CONCURRENTLY` | PostgreSQL | Cannot run inside a transaction block |
| `DROP INDEX CONCURRENTLY` | PostgreSQL | Cannot run inside a transaction block |
| `REINDEX CONCURRENTLY` | PostgreSQL | Cannot run inside a transaction block |
| `VACUUM` | PostgreSQL | Cannot run inside a transaction block |
| `CREATE DATABASE` / `DROP DATABASE` | PostgreSQL | Cannot run inside a transaction block |
| `CREATE TABLESPACE` / `DROP TABLESPACE` | PostgreSQL | Cannot run inside a transaction block |
| `ALTER SYSTEM` | PostgreSQL | Cannot run inside a transaction block (SQLSTATE 25001); the write to `postgresql.auto.conf` is non-transactional |
| `CREATE SUBSCRIPTION` / `DROP SUBSCRIPTION` | PostgreSQL | Cannot run inside a transaction block |
| `CLUSTER` | PostgreSQL | Cannot run inside a transaction block |
| Any DDL statement | Oracle | Oracle DDL is non-transactional — it implicitly commits |
| `CREATE DATABASE` / `DROP DATABASE` | DB2 | Cannot run inside a transaction; must be the first statement |
| `REORG` | DB2 | Cannot run inside a transaction |
| `RUNSTATS` | DB2 | Cannot run inside a transaction |

For Oracle, because **any** DDL statement implicitly commits, auto-detection treats the presence of DDL as a skip trigger; DML-only files are still wrapped.

Matching is **case-insensitive** (e.g. `create trigger` also matches). This list is not exhaustive and may be extended per RDBMS driver. When auto-detection triggers, a `[warn]` message is printed:

```
[warn] 20260103223344245:01  wrapping skipped (non-transactional statement detected)
```

## Stripping existing transaction commands

When wrapping is active, the tool **may** remove existing transaction control statements from the file content before wrapping — **only if enabled in config** (see below).

### Stripped commands (default regex patterns)

| Pattern | Description |
|---|---|
| `^\s*BEGIN(?:\s+TRAN(SACTION)?|\s+WORK)?\s*;?\s*$` | `BEGIN TRAN`, `BEGIN TRANSACTION`, `BEGIN WORK`. The optional group also lets a **bare `BEGIN`** match — but only on **SQLite and PostgreSQL**, where bare `BEGIN` is unambiguously a transaction statement. **DB2** has no `BEGIN` transaction form at all (implicit units of work) and a bare `BEGIN` starts a `BEGIN ATOMIC` compound statement, so nothing is matched there. **Oracle** never strips bare `BEGIN` — it starts a PL/SQL block. **MySQL**: bare `BEGIN` is documented as a session-level alias of `START TRANSACTION`, but it is *also* the compound-statement keyword in stored-program bodies (`CREATE`/`ALTER PROCEDURE`/`FUNCTION`/`TRIGGER`/`EVENT`); because the scanner does not track compound-block depth, MySQL does **not** strip bare `BEGIN` (the unambiguous `BEGIN WORK` form still matches). A file that relies on the bare-`BEGIN` alias must not enable stripping for that statement |
| `^\s*START\s+TRAN(SACTION)?\s*;?\s*$` | `START TRAN` / `START TRANSACTION` (a bare `START` is never matched) |
| `^\s*(?:COMMIT|ROLLBACK)(?:\s+TRAN(SACTION)?|\s+WORK)?\s*;?\s*$` | `COMMIT` / `ROLLBACK` (with optional `TRAN` / `TRANSACTION` / `WORK`) |
| `^\s*END\s+(?:TRAN(SACTION)?|WORK)\s*;?\s*$` | `END [TRANSACTION]` (SQLite), `END [WORK | TRANSACTION]` (PostgreSQL). DB2 has no `END` transaction form — it uses `COMMIT [WORK]` only, already covered above. A bare `END` is **not** stripped — it can terminate a PL/SQL or PL/pgSQL block |
| `^\s*SET\s+XACT_ABORT\s+(ON|OFF)\s*;?\s*$` | `SET XACT_ABORT ON/OFF` |

The patterns intentionally cover **only the plain forms shown** and are line-anchored: variants such as SQLite `BEGIN IMMEDIATE/EXCLUSIVE/DEFERRED`, PostgreSQL/MySQL `BEGIN ... ISOLATION LEVEL ...` or `START TRANSACTION ... READ WRITE/READ ONLY`, `COMMIT`/`ROLLBACK ... AND [NO] CHAIN` / `RELEASE`, and any of the above followed by a trailing inline comment are **not** stripped. For most engines this is a safe false negative — the wrapper still opens its own transaction, and an unstripped nested command inside the file is the file author's responsibility (or use `-- @nowrap`). On **MySQL** it is not purely safe: an unstripped session-level `BEGIN` or `COMMIT` inside the wrapped file implicitly **commits** the wrapper's already-open transaction (they are aliases of `START TRANSACTION`), so earlier statements in the file can be committed despite the wrap — file authors must not rely on bare `BEGIN` / `COMMIT` in MySQL files when wrapping is active.

Rules:
- Matching is case-insensitive.
- Only stripped when the command appears at the **start of a line** (ignoring leading whitespace).
- Line-end semicolon is optional.
- Lines inside SQL string literals or SQL block comments (`/* ... */`) are **not** stripped.
- Honoring the previous rule requires tracking lexical state — a bare line-anchored regex is **not** sufficient. The implementation must scan the file tracking, at minimum: single-quoted string literals (`'...'`, with `''` escapes, and — on MySQL and PostgreSQL `E'...'` strings — backslash escapes), PostgreSQL **dollar-quoted strings** (`$$...$$` and `$tag$...$tag$`), delimited identifiers (`"..."`, `` `...` ``, `[...]`), `--` line comments, and `/* ... */` block comments (including **nested** block comments on engines that support nesting — PostgreSQL, Oracle). A match counts only when the line starts outside all of those contexts. A `COMMIT` that appears inside a string literal or a PL/pgSQL body is data, not a transaction command.
- **Known limitation**: compound-block bodies are not tracked. A line-start `COMMIT` / `ROLLBACK` / `END` inside a stored-program body (PL/SQL `BEGIN ... END;`, MySQL `CREATE`/`ALTER PROCEDURE`/`FUNCTION`/`TRIGGER`/`EVENT` bodies, T-SQL `BEGIN ... END`, DB2 `BEGIN ATOMIC`) is treated as a transaction command and stripped. Files containing stored programs should use `-- @nowrap` or disable `transaction.strip`.

### Configurability

Auto-stripping is **disabled by default** in the public tool, because removing SQL from arbitrary files can be risky. Enable it explicitly per named database config (see [Transaction options](05-configuration.md#transaction-options)):

```yaml
default:
  engine: mssql
  server: localhost
  transaction:
    strip: true
    strip_patterns:
      - "^\\s*BEGIN\\s+TRAN"
      - "^\\s*COMMIT"
```

| Field | Default | Description |
|---|---|---|
| `transaction.strip` | `false` | Enable stripping of existing transaction commands |
| `transaction.strip_patterns` | default regexes above | Custom regex patterns for what to strip |

This prevents conflicts between user-managed and tool-managed transactions.

## Processing order

1. Read raw file content.
2. Process `-- @if` / `-- @else` / `-- @endif` conditionals.
3. Check for `-- @nowrap` (first line) — if present, skip steps 5–6.
4. Auto-detect non-transactional statements — if found, skip steps 5–6.
5. If `transaction.strip` is enabled, strip matching transaction control statements.
6. Wrap in `BEGIN TRANSACTION` / `COMMIT TRANSACTION` block.
7. Execute (driver manages `ROLLBACK` on error).
