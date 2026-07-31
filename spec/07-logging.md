# Logging & Output

## Message levels

All user-facing messages follow a standard prefix format printed to **stdout**. Exception: `versions` output and any `check` integrity report use their own machine-readable layouts (see [versions](04-commands.md#versions) and [check](04-commands.md#check)); the prefixes below apply to every other message.

| Level | Prefix | Color | Usage |
|---|---|---|---|
| `debug` | `[debug]` | Dim / gray | Internal details, verbose logs |
| `info` | `[info]` | Green | Normal progress, migration applied |
| `warning` | `[warn]` | Yellow | Non-blocking issues, irreversible migration skipped |
| `error` | `[error]` | Red | Failures, SQL errors, missing files |

## Verbosity

- `[debug]` messages are hidden by default.
- Enable with `--verbose` / `-v` (repeatable for more detail) or the `PSMT_VERBOSE` env var (see [Global flags](04-commands.md#global-flags)).

## Color

- Colors are enabled by default when stdout is a TTY.
- Disabled when `--no-color` flag is passed or `NO_COLOR` env var is set.
- Use ANSI escape codes (no external dependency).

## Examples

```
[info] 20260103223344245:01  migrated
[warn] 20260105120000000:02  has no undo file, irreversible
[error] 20260107151515000:01  SQL error: relation "users" already exists
[error] psmt migrate completed (3 applied, 0 skipped, 1 error)
```

## Summary line

Every `migrate` and `rollback` run finishes with a summary line:

```
[info] psmt {command} completed ({applied} applied, {skipped} skipped, {errors} errors)
```

The nouns are singularized when the count is `1` (`1 applied`, `1 skipped`, `1 error`); counts of `0` and `2+` use the plural form. The summary is printed at `[info]` on success.

If `errors > 0`, the summary uses `[error]` level and the process exits with code 1.
