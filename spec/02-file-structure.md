# File Structure

## Directory layout

```
migrations/
├── 20260103223344245_add_users_table/
│   ├── 01_create_users__do.sql
│   ├── 01_create_users__undo.sql
│   ├── 02_add_email_index__do.sql
│   └── 02_add_email_index__undo.sql
├── 20260105120000000_add_posts_table/
│   ├── 01_create_posts__do.sql
│   ├── 01_create_posts__undo.sql
│   └── 02_add_foreign_key__do.sql
│       (no undo — irreversible)
└── ...
```

## Folder naming

```
{main_version}_{description}
```

| Part | Format | Example |
|---|---|---|
| `main_version` | Safe charset `[A-Za-z0-9-]` (letters, digits, hyphens) | `20260103223344245`, `2026-alpha-01` |
| `description` | Safe charset `[A-Za-z0-9._-]` | `add_users_table` |

- `main_version` is the primary version identifier; `generate` produces a digits-only timestamp, but the folder may be renamed to any `main_version` within the charset `[A-Za-z0-9-]` (letters, digits, hyphens — no underscores, no empty value). Renaming does not affect `_migration` consistency as long as the folder keeps its `{main_version}_{description}` shape and remains unique.
- Ordering is **string-based** and is the only ordering — `main_version` may be non-numeric (see [Execution Semantics](06-execution-semantics.md)), so no padding/width conventions apply to it.
- The separator between `main_version` and `description` is the **first** underscore `_` — `main_version` is everything before the first `_`.
- `main_version` must be **unique across all folders** in the migrations directory. Two folders with the same `main_version` are a fatal integrity error: `check` reports it, and `migrate` / `rollback` / `preview` / `versions` abort with an `[error]` before doing any work (a `_migration` primary key cannot distinguish them).
- **Non-conforming folders** (no `_`, a `main_version` containing characters outside the safe charset `[A-Za-z0-9-]`, an **empty `main_version`** — i.e. a folder starting with `_`, an empty `description`, or a `description` containing characters outside the safe charset `[A-Za-z0-9._-]`) are never classified into a version and are ignored by `migrate` / `rollback` / `preview` / `versions` / `generate` the same way non-conforming files are. `check` reports each one as an integrity warning (see [check](04-commands.md#check)).
- `description` may start or end with an underscore; there is no restriction beyond the safe charset.

## File naming

```
{sub_version}_{description}__{direction}.sql
```

| Part | Format | Example |
|---|---|---|
| `sub_version` | Safe charset `[A-Za-z0-9-]` (letters, digits, hyphens) | `01`, `alpha-1` |
| `description` | Safe charset `[A-Za-z0-9._-]` | `create_users`, `add_email_index` |
| `direction` | `do` or `undo` | `do`, `undo` |

- `sub_version` is the version within a folder; `generate` scaffolds it as digits (`01`), but it may be renamed to any `sub_version` within the charset `[A-Za-z0-9-]` (letters, digits, hyphens — no underscores, no empty value). Ordering is **string-based** and is the only ordering (see [Execution Semantics](06-execution-semantics.md)), so no padding/width conventions apply to it.
- A **non-conforming file** is any `.sql` file in a conforming folder that does not fully match the pattern: a `sub_version` containing characters outside the safe charset `[A-Za-z0-9-]`, a `description` outside the safe charset `[A-Za-z0-9._-]`, a `direction` other than `do` / `undo` (case-sensitive — `DO`, `Do`, `UNDO` are non-conforming), an extension that is not exactly lowercase `.sql` (e.g. `undo.SQL`), an empty `sub_version` or `description`, or no `__` (so no direction part can be extracted). Non-conforming `.sql` files are ignored by `migrate` / `rollback` / `preview` / `versions` and reported by `check`. Files whose extension is not a `.sql` variant (e.g. `README.md`, `01_x__do.txt`) are not SQL files at all and are silently ignored by every command, including `check`.
- `sub_version` is everything before the **first** underscore `_` in the file name.
- The **last** double underscore `__` in the file name separates the description from the direction (the description may itself contain single or double underscores). Everything after that last `__`, minus the `.sql` extension, must be `do` or `undo`; anything else is a non-conforming file.
- `do` files are applied during migration.
- `undo` files are applied during rollback.
- A do file's **matching undo file** has the same `{sub_version}_{description}` prefix with direction `undo` — e.g. `01_create_users__do.sql` ↔ `01_create_users__undo.sql`.
- An undo file may be omitted for irreversible migrations.
