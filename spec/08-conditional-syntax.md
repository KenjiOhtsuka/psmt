# Conditional SQL

## Directives

Inline comments in SQL files control which parts are included based on the active environment (`-e, --env` flag).

| Directive | Example | Meaning |
|---|---|---|
| `-- @if {env_list}` | `-- @if dev, prod` | Include block if active env matches `dev` or `prod` |
| `-- @if not({env_list})` | `-- @if not(dev)` | Include block if active env is **not** `dev` |
| `-- @else` | `-- @else` | Block used when `-- @if` condition is false |
| `-- @endif` | `-- @endif` | Ends a conditional block |

## Rules

- `-- @if` lines are **not** included in the output.
- `-- @else` is optional. If omitted and the condition is false, the block is silently dropped.
- Nesting is **supported** — `-- @if` blocks can be nested inside other `-- @if` blocks. Each `-- @endif` closes the most recent open `-- @if`.
- `-- @else` binds to the **innermost** currently-open `-- @if`.
- Environment names are case-sensitive.
- Environment list is comma-separated; whitespace is optional: `-- @if dev,prod` and `-- @if dev, prod` are equivalent.
- `not()` can list multiple envs: `-- @if not(dev, staging)`.
- If `--env` is not specified, the active environment defaults to `default` (or `PSMT_ENV` when set — see [Configuration](05-configuration.md)).
- A file's conditionals are **well-formed** when every `-- @if` has a matching `-- @endif`, every `-- @else` appears inside an open block and at most once per block, and no `-- @endif` appears without an open block. A violation is a fatal `[error]` for `migrate` / `rollback` / `preview` (the file is aborted) and a fatal finding for `check`.
- Directives are recognized only when the `--` occurs **outside** SQL string literals and comments. The implementation must track lexical state (single-quoted strings with `''` escapes, delimited identifiers, `--` line comments, `/* */` block comments) — a `'-- @endif'` inside a string literal is data, not a directive.

## Examples

### Simple conditional

```sql
CREATE TABLE users (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
    -- @if dev, staging
    , email TEXT NOT NULL DEFAULT ''
    -- @endif
    -- @if prod
    , email TEXT NOT NULL UNIQUE
    -- @endif
);
```

With `--env dev`, the rendered output is:

```sql
CREATE TABLE users (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
    , email TEXT NOT NULL DEFAULT ''
);
```

### Nested conditionals

```sql
-- @if dev
-- @if not(ci)
GRANT ALL ON users TO dev_team;
-- @endif
-- @endif
```

With `--env dev` (not `ci`), the output is:

```sql
GRANT ALL ON users TO dev_team;
```

With `--env ci`, the inner block is excluded.

## Usage

Conditionals are processed by `migrate`, `rollback`, and `preview` commands.

## Limitation

Only `--` line-comment style directives are supported. MySQL's `#` comment style is **not** recognized for directives — use `-- @if` on MySQL too.
