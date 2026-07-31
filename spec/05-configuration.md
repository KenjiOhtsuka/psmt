# Configuration

## Method

**One config file per environment.** The environment is selected with `-e, --env` (default: `default`) or `PSMT_ENV`, and determines both the config file to load and the active environment name for conditional SQL (`-- @if`).

Config files live in the project's `config/` directory. The environment is the file base name.

### File naming per environment

| Environment | YAML | JSON | dotenv |
|---|---|---|---|
| `default` (no `--env`) | `config/default.yml` | `config/default.json` | `config/.env` |
| `dev` | `config/dev.yml` | `config/dev.json` | `config/.env.dev` |
| `prod` | `config/prod.yml` | `config/prod.json` | `config/.env.prod` |

### Config file search

- The environment name must match the safe charset `[A-Za-z0-9._-]`. Anything else is a usage error — rejected with `[error] invalid environment name: {env}` and exit `2` — consistent with other malformed flag values (see [Exit codes](04-commands.md#exit-codes)). This prevents path traversal when resolving `config/{env}.yml` (config resolution uses the raw name; see [preview output safety](04-commands.md#output-to-file) for the write-side sanitization).
- For the selected environment, walk up from the current working directory to the filesystem root. At each level, if a `config/` directory exists, look for the YAML, then JSON, then dotenv file inside it. The first file found is used — **directory level takes precedence over format**: a YAML in the working directory beats a JSON in a parent directory.
- If no config file is found for the environment at any level, the tool fails with `[error] config file not found: config/{env}.yml` (or `.json` / `.env` for the `default` environment, `.env.{env}` otherwise) and exits `1`.

### Precedence (highest to lowest)

1. CLI selection flags when given (`--env`, `--db`) and `--dir`
2. Environment variables
3. Config file
4. Built-in defaults

Connection fields (`engine`, `server`, `port`, `user`, `password`, `database`, `connection_string`, `auth`, `auth_params`, `charset`, and the `transaction.*` options) are resolved by env vars → config file → built-in defaults and are **not** overridable via CLI flags. `--dir` is the single exception — it overrides `migrations_dir` for filesystem operations (see [CLI flags](#cli-flags)).

## Content: named database configurations

The config file's top level is a **map of named database configurations**. Each named config is self-contained — engine, connection, and migration directory — which is what allows the same tool to manage multiple databases with separate histories.

### `config/default.yml` (default environment)

```yaml
default:
  engine: postgresql
  server: localhost
  port: 5432
  user: app
  password: ""
  database: myapp
  auth: password

db_2:
  engine: mysql
  server: 10.0.0.5
  port: 3306
  user: app
  password: ""
  database: other_app

azure:
  engine: mssql
  auth: azure
  auth_params:
    method: ActiveDirectoryIntegrated
  connection_string: "Driver={ODBC Driver 18 for SQL Server};Server=tcp:server.database.windows.net,1433;Database=mydb;Uid=user@server;Encrypt=yes;"
  database: mydb
```

(The example configs above use `auth: password` — SQL auth — unless `auth: azure` is present. Azure AD auth is selected per named config with `auth: azure` plus an `auth_params.method`, as shown in the `azure:` example.)

### `config/prod.yml` (production environment)

```yaml
default:
  engine: postgresql
  server: prod-db.example.com
  database: myapp_prod
  user: app
  password: ""

db_2:
  engine: mysql
  server: 10.0.1.5
  database: other_prod
```

## Per-config fields

| Field | Default | Description |
|---|---|---|
| `engine` | `postgresql` | RDBMS engine (see [engine values](#engine-values)) |
| `server` | `localhost` | Host name or address |
| `port` | per-engine default | Connection port |
| `user` | — | Login user. For Oracle, the special value `/` selects SYSDBA mode (see [Oracle SYSDBA mode](#oracle-sysdba-mode)) |
| `password` | — | Login password |
| `database` | — | Database name |
| `connection_string` | — | Full driver connection string; overrides `server` / `port` / `user` / `password` |
| `charset` | per-engine default | Database/server charset (see [Charset](#charset)) |
| `auth` | `password` | Authentication method (see [Authentication](#authentication)) |
| `auth_params` | — | Extra auth options (see [Authentication](#authentication)) |
| `migrations_dir` | `./migrations` | Migration directory for this database |

## `.env` format

`config/.env` (or `config/.env.{env}`) uses `KEY=VALUE` lines. Keys map to the same fields as environment variables (see [Environment variable fallbacks](#environment-variable-fallbacks)). A dotenv file configures the **`default`** named database.

```
PSMT_ENGINE=postgresql
PSMT_SERVER=localhost
PSMT_USER=app
PSMT_PASSWORD=secret
PSMT_DATABASE=myapp
PSMT_DIR=./migrations
```

- Values in the dotenv file do **not** override environment variables that are already set (override=false semantics).
- The dotenv file always populates the **`default`** named database config, regardless of the selected `--db` / `PSMT_DB`. It cannot configure other named databases. Real environment variables are different: they override the fields of the **selected** named config (`--db` / `PSMT_DB`; `default` when unset) — they do not apply to `default` specifically.
- A dotenv file is **exclusive with YAML/JSON** *at the same directory level*: at a given level the search order is YAML → JSON → dotenv, and the first file found wins. A nearer-level file therefore takes precedence regardless of format (a YAML in the working directory beats a JSON in a parent directory, and a dotenv in the working directory beats a YAML in a parent directory). Consequence: to keep secrets in `.env` for an environment, do **not** also create the YAML/JSON file for that environment at the same level — or keep the secrets in real environment variables, which always take precedence.
- **Selection and behavior keys** (`PSMT_DB`, `PSMT_ENV`, `PSMT_VERBOSE`, `NO_COLOR`) are **ignored** when read from a dotenv file — they are only honored as real environment variables. Only connection and directory keys (all other `PSMT_*` keys — `PSMT_ENGINE` through `PSMT_TRANSACTION_STRIP` — including the per-config `transaction.strip` fallback) populate the `default` named config.

## Databases and commands

| Command | Targets |
|---|---|
| `psmt generate migration db_2` | named config `db_2` |
| `psmt migrate` | named config `default` |
| `psmt migrate --db db_2` | named config `db_2` |
| `psmt db create` | named config `default` |
| `psmt db create db_2` | named config `db_2` |

If the selected named config does not exist in the resolved config file, the tool fails with `[error] database config not found: {db_key}` and exits `1`.

The syntax is not uniform by design: `generate`, `db create`, and `db destroy` take the named database config as a **positional argument** (`psmt generate migration db_2`, `psmt db create db_2`), while `migrate`, `rollback`, `check`, `preview`, and `versions` use the `--db` flag. Both default to `default`. `--db` is not accepted on the positional commands, and a positional is not accepted on the flag-based commands.

## Connection string style

A full connection string can be used instead of individual fields — essential for Azure SQL Server, where ODBC connection strings carry driver-specific options (`Encrypt`, `TrustServerCertificate`, `Connection Timeout`, etc.).

```json
{
  "azure": {
    "engine": "mssql",
    "connection_string": "Driver={ODBC Driver 18 for SQL Server};Server=tcp:server.database.windows.net,1433;Database=mydb;Uid=user@server;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
    "database": "mydb"
  }
}
```

Rules:
- `connection_string` **overrides** the individual fields when both are present — and it wins even over env-var values for those fields (e.g. a config `connection_string` with an embedded `PWD=` plus a `PSMT_PASSWORD` env var does not merge; the connection string is used as-is). The individual fields fall back to env vars → config only when no `connection_string` resolves.
- `database` is still used for `db create` / `db destroy` (server-level operations need the database name separately; the `Database=` part of the string is stripped for server-level connections).

## Charset

Per named database config, `charset` sets the database charset and the client-session charset.

| Engine | Default | Used for |
|---|---|---|
| MySQL / MariaDB | `utf8mb4` | `CREATE DATABASE ... CHARACTER SET {charset}` (db create) and the client session charset (`SET NAMES {charset}`) |
| PostgreSQL | `UTF8` | `CREATE DATABASE ... ENCODING '{charset}'` (db create) — encoding is fixed at creation |
| DB2 | `UTF8` | `CREATE DATABASE ... USING CODESET {charset}` (db create) — codeset is fixed at creation |
| Oracle | `AL32UTF8` | Informational only — db create is schema-based (see [db create](04-commands.md#db-create)), and the client charset is set via NLS/LDAP rather than per-connection |
| SQL Server | — | Not used (database collation is set at creation, out of scope) |
| SQLite | — | Not used (SQLite stores text as UTF-8 internally) |

The client-session charset is applied on every connection where the driver supports it (MySQL, PostgreSQL).

```yaml
default:
  engine: mysql
  charset: utf8mb4
  ...
```

## Authentication

| `auth` | Description |
|---|---|
| `password` (default) | Plain SQL login via `user` / `password`. For non-Azure servers, **no** `Authentication=` ODBC keyword is added |
| `azure` | Azure Active Directory auth. The `Authentication=` ODBC keyword is added per `auth_params.method` |

`auth_params`:

| Field | Default | Description |
|---|---|---|
| `auth_params.method` | `ActiveDirectoryIntegrated` | Azure AD variant: `ActiveDirectoryPassword`, `ActiveDirectoryIntegrated`, `ActiveDirectoryInteractive`, `ActiveDirectoryServicePrincipal`, `ActiveDirectoryDefault` |
| `auth_params.client_id` | — | For `ActiveDirectoryServicePrincipal` |
| `auth_params.client_secret` | — | For `ActiveDirectoryServicePrincipal` (prefer env var) |
| `auth_params.tenant_id` | — | For `ActiveDirectoryServicePrincipal` |
| `auth_params.trust_server_certificate` | `false` | MSSQL only: append `TrustServerCertificate=yes` to the ODBC connection string. Certificate validation stays on unless this is explicitly enabled (needed for servers with self-signed certs, e.g. local test containers). Env var: `PSMT_AUTH_TRUST_SERVER_CERTIFICATE` |

Password sources for azure:
- `ActiveDirectoryPassword` reuses the same `user` / `password` fields as SQL auth — the `password` comes from `password` / `PSMT_PASSWORD`, passed to the driver as the `PWD=` ODBC keyword.
- `ActiveDirectoryServicePrincipal` uses `auth_params.client_id` as the user, `auth_params.client_secret` (prefer `PSMT_AUTH_CLIENT_SECRET`) as the password, and `auth_params.tenant_id` (prefer `PSMT_AUTH_TENANT_ID`) passed to the driver via the `TenantID=` ODBC keyword.
- `ActiveDirectoryDefault` means "let the ODBC driver pick": it behaves like `ActiveDirectoryIntegrated` when the driver/OS supports it, otherwise falls back per driver rules. The tool sets the `Authentication=ActiveDirectoryDefault` ODBC connection keyword and sends **no** password — there is no fixed guarantee about which underlying method is chosen, so prefer an explicit method in automation.

For password auth, prefer `PSMT_PASSWORD` env var over storing it in the config file.

## Connection modes

The tool always connects in-process through the engine's Python driver. There is **no external command-line driver** and no subprocess delegation — authentication (including Azure AD) is handled entirely by the driver, so credentials never appear in a process list or argv.

### Driver dependencies

| Engine | Library | Install extra | System dependencies |
|---|---|---|---|
| PostgreSQL | `psycopg` v3 (`psycopg[binary]`) | `pip install "psmt[postgresql]"` | none (prebuilt wheels); `psycopg2-binary` is also compatible |
| MySQL | `PyMySQL` | `pip install "psmt[mysql]"` | none (pure Python) |
| SQLite | stdlib `sqlite3` | — (built-in) | none |
| SQL Server | `pyodbc` | `pip install "psmt[mssql]"` | Microsoft ODBC Driver 17/18 |
| Oracle | `oracledb` | `pip install "psmt[oracle]"` | none in thin mode (default); thick mode needs Oracle Client |
| DB2 | `ibm_db` | `pip install "psmt[db2]"` | IBM DB2 client libraries (`clidriver`) |

- The base package installs **no third-party database drivers** — only stdlib `sqlite3`.
- Drivers are **imported lazily**: only the driver for the target engine is loaded, at connect time. A user who only uses PostgreSQL never imports the MySQL, mssql, Oracle, or DB2 drivers.
- If the driver for the target engine is not installed, the tool fails with `[error] driver not installed for engine {engine}; install with: pip install "psmt[{extra}]"` and exits `1`.
- `pip install "psmt[all]"` installs every driver. The extras are mutually independent, so `"psmt[postgresql]"` installs only the PostgreSQL driver plus its system dependency.
- `psmt[mssql]` and `psmt[all]` also install `azure-identity`, which is needed only for `ActiveDirectoryServicePrincipal` (MSAL-based token acquisition, see [Azure AD authentication (mssql)](#azure-ad-authentication-mssql)). If it is missing at connect time (e.g. a hand-built environment), the tool fails with `[error] azure-identity not installed; install with: pip install "psmt[mssql]"` and exits `1`.

### Azure AD authentication (mssql)

`pyodbc` + Microsoft ODBC Driver 17/18 supports Azure AD **in-process** — no subprocess or CLI delegation; the only external surface is the browser prompt for `ActiveDirectoryInteractive` (and a pre-existing `az login` session for integrated auth). The `Authentication=` connection keyword (derived from `auth` + `auth_params`) selects the method. Method support depends on the ODBC driver version and environment:

- `ActiveDirectoryPassword` / `ActiveDirectoryServicePrincipal` — work with ODBC 17/18; the service-principal variant acquires tokens via MSAL through `azure-identity` (installed by the `psmt[mssql]` / `psmt[all]` extras — see [Driver dependencies](#driver-dependencies)).
- `ActiveDirectoryIntegrated` — relies on the user already being signed in (`az login` / Windows SSO).
- `ActiveDirectoryInteractive` — opens a browser prompt; impractical in automation — use a service principal instead.

Because the driver runs in-process, the password and service-principal secret are passed to the ODBC driver via connection keywords (`PWD=`, `ClientSecret=`) — never through a command line, so nothing leaks through the process list.

## Multiple migration directories

- Each named database config has its own `migrations_dir`.
- This supports the case where separate databases are maintained with separate migration histories.
- A **relative** `migrations_dir` (or `-d` value) resolves against the process current working directory — **not** the config file's directory. This keeps behavior identical whether the config was found in `./config/` or in an ancestor `config/` directory.

## Transaction options

Per named database config (or inherited built-in defaults):

| Field | Default | Description |
|---|---|---|
| `transaction.strip` | `false` | Strip existing transaction control statements before wrapping (see [Transaction Wrapping](09-transaction-wrapping.md)) |
| `transaction.strip_patterns` | built-in default regexes | Custom regex patterns used for stripping. Empty array `[]` = use the built-in default patterns |

## Secrets

- The `password` field in config files is stored in plaintext.
- Recommended: add `config/` to `.gitignore` (or store it outside the repo) when the files contain credentials.
- **Credential redaction**: passwords are **never** written at `[debug]` verbosity and never echoed in error messages. Connection errors show the host and a redacted summary (e.g. `[error] connection failed: server=prod-db.example.com (password redacted)`). A connection string may appear at `[debug]`, but only with credential keywords masked: `Pwd=`, `password`, `ClientSecret=`, `Secret=` → `***`. The masking is applied to any output that includes a resolved connection string or driver keyword list.

## `engine` values

| Value | Default port |
|---|---|
| `postgresql` | 5432 |
| `mysql` | 3306 |
| `sqlite` | — |
| `mssql` | 1433 |
| `oracle` | 1521 |
| `db2` | 50000 |

**Oracle SYSDBA mode**: `db create` / `db destroy` for the `oracle` engine connect as `/` (SYSDBA) and manage a *schema*, not a database (see [db create](04-commands.md#db-create)). Set `user: "/"` to select SYSDBA mode — the tool passes `AUTH_MODE_SYSDBA` to oracledb. `user: "/"` is valid only for the `oracle` engine and is rejected with an `[error]` for any other engine. `db create` emits no `DEFAULT TABLESPACE` clause (the instance's default tablespace is used) and grants the new schema an unlimited quota on that tablespace.

## CLI flags

CLI flags do **not** override connection fields — connection settings are configured only via the config file or environment variables (see [Precedence](#precedence-highest-to-lowest)).

Selection flags only:

| Flag | Purpose |
|---|---|
| `-e, --env` | Select environment (config file + conditional SQL) |
| `--db` | Select named database config |
| `-d, --dir` | Override `migrations_dir` (filesystem operations) — the one field a CLI flag can override |

## Environment variable fallbacks

| Env var | Maps to |
|---|---|
| `PSMT_ENGINE` | `engine` |
| `PSMT_SERVER` | `server` |
| `PSMT_PORT` | `port` |
| `PSMT_USER` | `user` |
| `PSMT_PASSWORD` | `password` |
| `PSMT_DATABASE` | `database` |
| `PSMT_CHARSET` | `charset` |
| `PSMT_AUTH` | `auth` |
| `PSMT_AUTH_METHOD` | `auth_params.method` |
| `PSMT_AUTH_CLIENT_ID` | `auth_params.client_id` |
| `PSMT_AUTH_CLIENT_SECRET` | `auth_params.client_secret` |
| `PSMT_AUTH_TENANT_ID` | `auth_params.tenant_id` |
| `PSMT_CONNECTION_STRING` | `connection_string` |
| `PSMT_DIR` | `migrations_dir` |
| `PSMT_DB` | named config selection |
| `PSMT_ENV` | environment name (config file selection + conditional SQL) |
| `PSMT_VERBOSE` | verbose output toggle (equivalent to `--verbose`; ignored in dotenv files) |
| `PSMT_TRANSACTION_STRIP` | `transaction.strip` (`"true"` / `"false"`) |
| `NO_COLOR` | color output toggle (see [Logging & Output](07-logging.md#color)); honored only as a real environment variable, ignored in dotenv files |

`transaction.strip_patterns` (an array) is config-only — no environment variable fallback.
