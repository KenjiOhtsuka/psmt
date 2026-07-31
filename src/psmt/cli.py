import argparse
import os
import sys
import traceback
from pathlib import Path

from . import check as check_mod
from . import config as config_mod
from . import dbadmin, generate, preview as preview_mod
from .config import select_db, select_env
from .drivers.registry import get_driver
from .exceptions import PsmtError, UsageError
from .executor import migrate, rollback, versions
from .executor.targets import parse_preview_version, parse_steps, parse_version_list
from .logging import Logger
from .version import __version__

_INIT_SKELETON = """default:
  engine: postgresql
  server: localhost
  port: 5432
  user: ""
  password: ""
  database: ""
  auth: password
  migrations_dir: {dir}
"""


class PsmtParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"psmt: [error] {message}", file=sys.stderr)
        raise SystemExit(2)


def _add_common(parser, tool_version=True):
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--no-color", action="store_true")
    if tool_version:
        parser.add_argument(
            "-V", "--version", "--tool-version", action="version", version=f"psmt {__version__}"
        )
    else:
        parser.add_argument(
            "-V", "--tool-version", action="version", version=f"psmt {__version__}"
        )


def _add_env_db_dir(parser, positional=False):
    parser.add_argument("-d", "--dir")
    parser.add_argument("-e", "--env")
    if positional:
        parser.add_argument("db_key", nargs="?")
    else:
        parser.add_argument("--db")


def build_parser():
    parser = PsmtParser(prog="psmt", description="Python SQL Migration Tool")
    parser.add_argument(
        "-V", "--version", "--tool-version", action="version", version=f"psmt {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    _add_common(p_init)
    p_init.add_argument("-d", "--dir", default="./migrations")

    p_generate = sub.add_parser("generate")
    _add_common(p_generate)
    p_generate.add_argument("artifact", nargs="?")
    p_generate.add_argument("db_key", nargs="?")
    p_generate.add_argument("-d", "--dir")
    p_generate.add_argument("-e", "--env")
    p_generate.add_argument("--summary")

    for name in ("migrate", "rollback"):
        p = sub.add_parser(name)
        _add_common(p, tool_version=False)
        _add_env_db_dir(p)
        p.add_argument("--version")
        p.add_argument("--steps")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--force", action="store_true")

    p_check = sub.add_parser("check")
    _add_common(p_check)
    _add_env_db_dir(p_check)
    p_check.add_argument("--no-grammar", dest="no_grammar", action="store_true")
    p_check.add_argument("--no-db", dest="no_grammar", action="store_true")

    p_preview = sub.add_parser("preview")
    _add_common(p_preview)
    _add_env_db_dir(p_preview)
    p_preview.add_argument("version", nargs="?")
    p_preview.add_argument("--undo", action="store_true")
    p_preview.add_argument("--no-tracker", action="store_true")
    p_preview.add_argument("--output")
    p_preview.add_argument("--raw", action="store_true")

    p_versions = sub.add_parser("versions")
    _add_common(p_versions)
    _add_env_db_dir(p_versions)

    p_db = sub.add_parser("db")
    _add_common(p_db)
    db_sub = p_db.add_subparsers(dest="db_command", required=True)
    p_create = db_sub.add_parser("create")
    _add_common(p_create)
    p_create.add_argument("db_key", nargs="?")
    p_create.add_argument("-e", "--env")
    p_destroy = db_sub.add_parser("destroy")
    _add_common(p_destroy)
    p_destroy.add_argument("db_key", nargs="?")
    p_destroy.add_argument("-e", "--env")
    p_destroy.add_argument("--force", action="store_true")

    return parser


def _verbose(args):
    count = getattr(args, "verbose", 0) or 0
    if os.environ.get("PSMT_VERBOSE"):
        count += 1
    return count


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = Logger(verbose=_verbose(args), no_color=bool(getattr(args, "no_color", False)))
    try:
        return _dispatch(args, logger)
    except PsmtError as exc:
        logger.error(str(exc))
        return exc.exit_code
    except KeyboardInterrupt:
        logger.error("interrupted")
        return 1
    except Exception as exc:
        logger.debug(traceback.format_exc())
        logger.error(str(exc))
        return 1


def _dispatch(args, logger):
    command = args.command
    if command == "init":
        return _cmd_init(args, logger)
    if command == "generate":
        return _cmd_generate(args, logger)
    if command == "migrate":
        return _cmd_apply(args, logger, "migrate")
    if command == "rollback":
        return _cmd_apply(args, logger, "rollback")
    if command == "check":
        return _cmd_check(args, logger)
    if command == "preview":
        return _cmd_preview(args, logger)
    if command == "versions":
        return _cmd_versions(args, logger)
    if command == "db":
        return _cmd_db(args, logger)
    raise UsageError(f"unknown command: {command}")


def _ctx(args, logger, positional=False):
    env = select_env(getattr(args, "env", None))
    if positional:
        db_key = args.db_key or os.environ.get("PSMT_DB") or "default"
    else:
        db_key = select_db(getattr(args, "db", None), None)
    cfg = config_mod.resolve_database_config(env, db_key, cli_dir=getattr(args, "dir", None))
    driver = get_driver(cfg.engine)
    from .executor import MigrationContext

    return MigrationContext(logger, env, db_key, cfg, driver, Path(cfg.migrations_dir))


def _cmd_init(args, logger):
    base = Path(args.dir)
    base.mkdir(parents=True, exist_ok=True)
    config_dir = Path("config")
    config_dir.mkdir(parents=True, exist_ok=True)
    for env in ("default", "dev", "prod"):
        target = config_dir / f"{env}.yml"
        if not target.exists():
            target.write_text(_INIT_SKELETON.format(dir=args.dir), encoding="utf-8")
    logger.info(f"initialized migration directory: {base}")
    return 0


def _cmd_generate(args, logger):
    db_key = args.db_key
    if args.artifact and args.artifact != "migration":
        db_key = args.artifact
    if db_key is None:
        db_key = os.environ.get("PSMT_DB") or "default"
    env = select_env(getattr(args, "env", None))
    cfg = config_mod.resolve_database_config(env, db_key, cli_dir=args.dir)
    folder = generate.run_generate(Path(cfg.migrations_dir), summary=args.summary)
    logger.info(f"created migration: {folder}")
    return 0


def _cmd_apply(args, logger, command):
    ctx = _ctx(args, logger)
    version_given = args.version is not None
    version = parse_version_list(args.version) if version_given else None
    steps_given = args.steps is not None
    if version_given and steps_given:
        raise UsageError("--version and --steps cannot be combined")
    steps = parse_steps(args.steps if args.steps is not None else ("1" if command == "rollback" else "all"))
    if command == "migrate":
        return 0 if migrate.run_migrate(ctx, version=version, steps=steps, dry_run=args.dry_run, force=args.force) else 1
    return 0 if rollback.run_rollback(ctx, version=version, steps=steps, dry_run=args.dry_run, force=args.force) else 1


def _cmd_check(args, logger):
    ctx = _ctx(args, logger)
    return check_mod.run_check(ctx, no_grammar=args.no_grammar)


def _cmd_preview(args, logger):
    ctx = _ctx(args, logger)
    if args.version is None:
        raise UsageError("preview requires a version {main}:{sub}")
    target = parse_preview_version(args.version)
    return preview_mod.run_preview(
        ctx,
        target,
        undo=args.undo,
        no_tracker=args.no_tracker,
        output_dir=args.output,
        raw=args.raw,
    )


def _cmd_versions(args, logger):
    ctx = _ctx(args, logger)
    versions.run_versions(ctx)
    return 0


def _cmd_db(args, logger):
    env = select_env(getattr(args, "env", None))
    db_key = args.db_key or os.environ.get("PSMT_DB") or "default"
    cfg = config_mod.resolve_database_config(env, db_key)
    driver = get_driver(cfg.engine)
    from .executor import MigrationContext

    ctx = MigrationContext(logger, env, db_key, cfg, driver, Path(cfg.migrations_dir))
    if args.db_command == "create":
        dbadmin.run_db_create(ctx)
    else:
        if not args.force:
            raise UsageError("--force is required to destroy the database")
        dbadmin.run_db_destroy(ctx)
    return 0
