# psmt — Python SQL Migration Tool

psmt is a lightweight, file-based SQL migration tool. It organizes raw SQL files
into versioned folders and tracks execution state in a `_migration` table inside
the target database.

- Plain `.sql` files — no DSL, no ORM.
- Engines: PostgreSQL, MySQL/MariaDB, SQL Server, SQLite, Oracle, DB2.
- In-process driver connections only (no subprocess delegation).

## Install

```sh
pip install psmt                 # core only (SQLite works out of the box)
pip install "psmt[all]"          # everything, including all engine drivers
```

Per-engine extras: `psmt[postgresql]`, `psmt[mysql]`, `psmt[mssql]`,
`psmt[oracle]`, `psmt[db2]`. SQLite needs no extra driver.

## Usage

```sh
psmt init
psmt generate migration default --summary "add user table"
psmt migrate
psmt rollback
psmt preview 20260103223344245:01
psmt versions
psmt check
psmt db create
psmt db destroy --force
```

## Tests

```sh
pytest -m "not integration"      # unit tests (no database needed)
docker compose -f docker/docker-compose.yml up -d   # provision test databases
pytest -m integration            # real-database tests (unreachable engines are skipped)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, the editable
install, and contribution guidelines. `spec/` contains the full design.
