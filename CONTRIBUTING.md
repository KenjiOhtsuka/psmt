# Contributing to psmt

## Development setup

psmt uses a `src/` layout and is installed as an editable package for
development:

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux

pip install -e ".[dev]"
pip install -e ".[all]"         # all engine drivers for integration tests
```

`psmt` is then available on the PATH:

```sh
psmt --tool-version
```

> On this machine the system Python's site-packages are write-protected, so use
> the project venv (`.venv\Scripts\python.exe`) for installs and tests.

## Project layout

```
src/psmt/            package code (library + cli.py)
  drivers/           one adapter per engine (connect/execute/dry-run)
  executor/          migrate / rollback / versions / preview targets
tests/unit/          pure unit tests (no database needed)
tests/integration/   real-database tests; unreachable engines are skipped
docker/              docker-compose.yml provisioning the six test databases
spec/                the authoritative design documents
issue.md             requirement/finding ledger
```

## Running the tests

Unit tests need no database:

```sh
python -m pytest -m "not integration"
```

Integration tests exercise the real engines. Provision the databases first:

```sh
docker compose -f docker/docker-compose.yml up -d
python -m pytest -m integration -v
```

Engines that are unreachable (driver not installed, or server not running) are
skipped, so the suite stays green locally. Credentials and connection settings
for the test databases live in `tests/integration/helpers.py` and are
overridable via `PSMT_TEST_*` environment variables.

## Design and conventions

- The specs in `spec/` (01-overview through 09-transaction-wrapping) are
  authoritative. Implementation changes that contradict a spec must update the
  spec first.
- Raw SQL is never generated from a DSL; migrations are plain `.sql` files.
- The tool connects in-process only; there is no external CLI delegation.
- Exit codes: 0 success, 1 operational error, 2 usage error. `check` reports
  0 clean / 1 integrity / 2 grammar.
- Version strings use `{main_version}:{sub_version}` (colon separator).
- Logging goes through `psmt.logging.Logger`; passwords and secrets are
  redacted. `NO_COLOR` and `PSMT_VERBOSE` are honored.
- Keep new SQL parsing in `sqlscan.py` (lexical state classifier) and extend it
  rather than adding ad-hoc regex parsing.
- New behavior should come with unit tests; engine-specific behavior goes in
  the per-engine driver and the integration matrix (`tests/integration/`).
- Keep `issue.md` current: mark findings fixed when they are resolved, use
  `- [ ]` checkboxes for open items.

## Before submitting

1. Run the full unit suite: `python -m pytest -m "not integration"` — it must
   pass.
2. If you touched engine behavior, run the integration suite against
   `docker compose -f docker/docker-compose.yml up -d`.
3. Update `spec/` if behavior changed, and `README.md` if user-facing
   instructions changed.
4. Do not commit generated artifacts (see `.gitignore`) or any secrets.
