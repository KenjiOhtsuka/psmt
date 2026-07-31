# psmt — Python SQL Migration Tool

## Overview

psmt is a lightweight, file-based SQL migration tool. It organizes raw SQL files into versioned folders and tracks execution state in a `_migration` table inside the target database.

The tool is designed to be simple, database-agnostic, and easy to audit. Each migration is a plain `.sql` file — no DSL, no ORM, no hidden state.

## Project

- **Name**: psmt (Python SQL Migration Tool)
- **Language**: Python
- **Database support**: PostgreSQL, MySQL/MariaDB, SQL Server, SQLite, Oracle, DB2

## Features

| Function | Description | Priority |
|---|---|---|---|
| `init` | Scaffold migration directories and config | Primary |
| `generate` | Create migration folder and file scaffolds | Primary |
| `migrate` | Apply all pending migrations | Primary |
| `rollback` | Revert applied migrations (undo) | Primary |
| `check` | Validate migration file integrity and SQL grammar | Primary |
| `preview` | Preview processed SQL for a given environment | Primary |
| `versions` | Show migration status (migrated / pending / orphaned) | Primary |
| `db create` | Create the target database | Secondary |
| `db destroy` | Drop the target database | Secondary |
