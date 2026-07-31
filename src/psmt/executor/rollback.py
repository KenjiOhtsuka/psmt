from .. import tracker
from ..exceptions import MigrationNotFoundError
from ..naming import collect_files
from .common import dry_run_file, execute_file, process_file_content, summary


def run_rollback(ctx, version=None, steps=None, dry_run=False, force=False):
    logger = ctx.logger
    driver = ctx.driver
    do_files = collect_files(ctx.migrations_dir, "do")
    undo_files = collect_files(ctx.migrations_dir, "undo")
    undo_by_key = {(f.main_version, f.sub_version): f for f in undo_files}
    conn = driver.connect(ctx.cfg)
    applied_count = skipped_count = error_count = 0
    try:
        applied = driver.fetch_applied(conn)
        if version is None:
            entries = sorted(applied, reverse=True)
            if steps is not None:
                entries = entries[:steps]
            targets = [(main, sub) for main, sub in entries]
        else:
            targets = _expand_rollback_targets(do_files, version)
            targets.sort(reverse=True)
        for main, sub in targets:
            key = f"{main}:{sub}"
            recorded = (main, sub) in applied
            if not recorded and not force:
                logger.info(f"{key}  not migrated")
                skipped_count += 1
                continue
            undo = undo_by_key.get((main, sub))
            if undo is None:
                logger.warn(f"{key}  has no undo file, irreversible")
                skipped_count += 1
                continue
            processed = process_file_content(ctx, undo.path, key)
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
            tracker_stmt = tracker.delete_statement(main, sub) if recorded else None
            try:
                execute_file(ctx, conn, processed, tracker_stmt)
            except Exception as exc:
                logger.error(f"{key}  SQL error: {exc}")
                error_count += 1
                break
            applied_count += 1
            logger.info(f"{key}  rolled back")
    finally:
        driver.close(conn)
    summary(logger, "rollback", applied_count, skipped_count, error_count)
    return error_count == 0


def _expand_rollback_targets(do_files, targets):
    subs_by_main = {}
    for f in do_files:
        subs_by_main.setdefault(f.main_version, []).append(f.sub_version)
    result = []
    seen = set()
    for target in targets:
        if target.main_version not in subs_by_main:
            raise MigrationNotFoundError(f"migration version not found: {target}")
        if target.sub_version is not None:
            if target.sub_version not in subs_by_main[target.main_version]:
                raise MigrationNotFoundError(f"migration version not found: {target}")
            pairs = [(target.main_version, target.sub_version)]
        else:
            pairs = [(target.main_version, sub) for sub in sorted(subs_by_main[target.main_version], reverse=True)]
        for main, sub in pairs:
            if (main, sub) not in seen:
                seen.add((main, sub))
                result.append((main, sub))
    return result
