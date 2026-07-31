from .. import tracker
from ..exceptions import MigrationNotFoundError
from ..naming import collect_files
from .common import dry_run_file, execute_file, process_file_content, summary
from .targets import utc_now_string


def run_migrate(ctx, version=None, steps=None, dry_run=False, force=False):
    logger = ctx.logger
    engine = ctx.cfg.engine
    driver = ctx.driver
    do_files = collect_files(ctx.migrations_dir, "do")
    conn = driver.connect(ctx.cfg)
    applied_count = skipped_count = error_count = 0
    try:
        driver.ensure_migration_table(conn)
        applied = driver.fetch_applied(conn)
        if version is None:
            if steps is not None:
                pending = [f for f in do_files if f.key not in applied]
                targets = pending[:steps]
            else:
                targets = do_files
        else:
            targets = _expand_migrate_targets(do_files, version)
        for f in targets:
            key = f"{f.main_version}:{f.sub_version}"
            recorded = f.key in applied
            if recorded and not force:
                logger.info(f"{key}  already migrated")
                skipped_count += 1
                continue
            processed = process_file_content(ctx, f.path, key)
            if dry_run:
                status, _ = dry_run_file(ctx, conn, key, processed)
                if status == "error":
                    error_count += 1
                    break
                if status == "skip":
                    skipped_count += 1
                else:
                    applied_count += 1
                continue
            utc = utc_now_string()
            if recorded and force:
                tracker_stmt = tracker.update_statement(
                    engine, f.main_version, f.sub_version, utc
                )
            else:
                tracker_stmt = tracker.insert_statement(engine, f.main_version, f.sub_version, utc)
            try:
                execute_file(ctx, conn, processed, tracker_stmt)
            except Exception as exc:
                logger.error(f"{key}  SQL error: {exc}")
                error_count += 1
                break
            applied_count += 1
            logger.info(f"{key}  migrated")
    finally:
        driver.close(conn)
    summary(logger, "migrate", applied_count, skipped_count, error_count)
    return error_count == 0


def _expand_migrate_targets(do_files, targets):
    result = []
    seen = set()
    for target in targets:
        matched = [
            f
            for f in do_files
            if f.main_version == target.main_version
            and (target.sub_version is None or f.sub_version == target.sub_version)
        ]
        if not matched:
            raise MigrationNotFoundError(f"migration version not found: {target}")
        for f in matched:
            if f.key not in seen:
                seen.add(f.key)
                result.append(f)
    return result
