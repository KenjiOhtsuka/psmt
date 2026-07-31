from . import conditional, naming, wrapping
from .exceptions import ConditionalError, OperationalError
from .executor.common import dry_run_file
from .naming import collect_files


def run_check(ctx, no_grammar=False):
    logger = ctx.logger
    if not ctx.migrations_dir.is_dir():
        raise OperationalError(f"migrations directory not found: {ctx.migrations_dir}")
    errors, warnings = _integrity_phase(ctx)
    for item in warnings:
        logger.warn(item)
    for item in errors:
        logger.error(item)
    if errors:
        logger.error(
            f"psmt check completed ({len(errors)} integrity errors, {len(warnings)} warnings)"
        )
        return 1
    if no_grammar:
        logger.info(f"psmt check completed (0 integrity errors, {len(warnings)} warnings)")
        return 0
    grammar_errors, grammar_warnings = _grammar_phase(ctx)
    for item in grammar_warnings:
        logger.warn(item)
    for item in grammar_errors:
        logger.error(item)
    if grammar_errors:
        logger.error(f"psmt check completed ({len(grammar_errors)} grammar errors)")
        return 2
    logger.info(f"psmt check completed (0 grammar errors, {len(warnings)} warnings)")
    return 0


def _integrity_phase(ctx):
    errors = []
    warnings = []
    folders, non_conforming_folders = naming.build_index(ctx.migrations_dir)
    for folder in non_conforming_folders:
        errors.append(f"{folder.name}: {folder.reason}")
    for main_version, folder_list in sorted(folders.items()):
        if len(folder_list) > 1:
            names = ", ".join(f.name for f in folder_list)
            errors.append(f"duplicate main_version: {main_version} ({names})")
    for folder in naming.conforming_folders(ctx.migrations_dir):
        files = naming.scan_files(folder)
        seen = {}
        for f in files:
            if not f.conforming:
                errors.append(f"{folder.name}/{f.path.name}: {f.reason}")
                continue
            pair = (f.sub_version, f.direction)
            if pair in seen:
                errors.append(
                    f"{folder.name}/{f.path.name}: duplicate {f.sub_version} {f.direction}"
                )
            seen[pair] = f.path.name
        pairs = naming.find_do_undo([f for f in files if f.conforming])
        for prefix, directions in sorted(pairs.items()):
            if "do" in directions and "undo" not in directions:
                warnings.append(f"{folder.name}/{directions['do'].path.name}: has no undo file, irreversible")
            elif "undo" in directions and "do" not in directions:
                warnings.append(f"{folder.name}/{directions['undo'].path.name}: has no matching do file")
    for f in collect_files(ctx.migrations_dir, "do") + collect_files(ctx.migrations_dir, "undo"):
        try:
            conditional.process_conditionals(f.path.read_text(encoding="utf-8"), ctx.env)
        except ConditionalError as exc:
            errors.append(f"{f.path.name}: {exc}")
    return errors, warnings


def _grammar_phase(ctx):
    errors = []
    warnings = []
    driver = ctx.driver
    conn = driver.connect(ctx.cfg)
    try:
        applied = driver.fetch_applied(conn)
        disk = {(f.main_version, f.sub_version) for f in collect_files(ctx.migrations_dir, "do")}
        for main, sub in sorted(applied - disk):
            warnings.append(f"orphaned _migration row: {main}:{sub}")
        for f in collect_files(ctx.migrations_dir, "do"):
            key = f"{f.main_version}:{f.sub_version}"
            processed = wrapping.process_file(
                f.path.read_text(encoding="utf-8"),
                ctx.cfg.engine,
                ctx.env,
                strip=ctx.cfg.transaction_strip,
                strip_patterns=ctx.cfg.transaction_strip_patterns,
            )
            if not processed.wrapped:
                ctx.logger.warn(f"{key}  wrapping skipped ({processed.reason})")
            status, _ = dry_run_file(ctx, conn, key, processed)
            if status == "error":
                errors.append(f"{f.path.name}: grammar error")
    finally:
        driver.close(conn)
    return errors, warnings
