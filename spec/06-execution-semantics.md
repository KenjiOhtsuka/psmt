# Execution Semantics

## Ordering

1. **Migration order**: Folders are sorted by `main_version` (string ascending). Within a folder, files are sorted by `sub_version` (string ascending). The sort is performed by the tool on the parsed values — it does **not** depend on filesystem ordering, and it is **not** numeric order (`1, 10, 2`). Both `main_version` and `sub_version` may contain letters, digits and hyphens (see [File Structure](02-file-structure.md)), so string order is the only order that applies — there is no numeric ordering and no padding/width convention.
2. **Rollback order**: Applied entries from `_migration` are sorted by `main_version` string-descending, then `sub_version` string-descending. The undo file for each matching entry is executed.

Ordering assumes `main_version` is unique across folders; duplicates are a fatal error (see [File Structure](02-file-structure.md)).

## Transaction handling

- Each SQL file is executed with tool-managed transaction wrapping by default. See [Transaction Wrapping](09-transaction-wrapping.md) for details.
- Each file is wrapped in its own transaction, so a failure in one file does **not** roll back files applied earlier in the same run — regardless of engine. There is no global transaction around a full `migrate` or `rollback` run.
- Where DDL is non-transactional (MySQL, Oracle), an individual failing file may also leave partially-applied DDL behind, because the DDL statements committed themselves before the error (see [Transaction Wrapping](09-transaction-wrapping.md)); transactional engines (PostgreSQL, SQLite, SQL Server, DB2) do not have this gap.

## Idempotency

- `migrate` only executes files whose `{main_version, sub_version}` pair is **not** in `_migration`.
- `rollback` only executes undo files for entries that **are** in `_migration`.
- Re-running `migrate` after a successful run is a no-op.
- Re-running `rollback` after a successful rollback is a no-op (nothing to roll back).
- Already-applied migrations print `[info] already migrated` and are skipped.
- Not-applied migrations during rollback print `[info] not migrated` and are skipped.
- `--force` bypasses these checks (see [Force](04-commands.md#force)).

## Irreversible migrations

- If a do file exists but the matching undo file does not, the migration is considered irreversible.
- `rollback` skips entries with no matching undo file and prints a warning.

## Dry-run

- `--dry-run` connects to the database and validates each statement using the RDBMS-specific method (see [Dry-run](04-commands.md#dry-run)).
- No migration is applied and `_migration` is not modified.
- If `--dry-run` is combined with `--version` or `--steps`, only the targeted files are validated.
