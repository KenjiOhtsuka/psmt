from .. import sqlscan, tracker, wrapping


def execute_file(ctx, conn, processed, tracker_stmt):
    engine = ctx.cfg.engine
    driver = ctx.driver
    if processed.wrapped and driver.uses_text_wrap:
        sql = wrapping.wrap_content(engine, processed.content, tracker_stmt)
        try:
            driver.execute(conn, sql)
        except Exception:
            driver.rollback(conn)
            raise
        return
    try:
        for stmt in sqlscan.split_statements(processed.content):
            driver.execute(conn, stmt)
        if processed.wrapped:
            if tracker_stmt:
                driver.execute(conn, tracker_stmt)
            driver.commit(conn)
        else:
            driver.commit(conn)
            if tracker_stmt:
                driver.execute(conn, tracker_stmt)
                driver.commit(conn)
    except Exception:
        driver.rollback(conn)
        raise


def dry_run_file(ctx, conn, key, processed):
    driver = ctx.driver
    if not processed.wrapped and not driver.dry_run_handles_unwrapped:
        return "skip", ""
    statements = sqlscan.split_statements(processed.content)
    outcomes = driver.dry_run(conn, statements)
    errors = 0
    for status, message in outcomes:
        if status == "error":
            errors += 1
            ctx.logger.error(f"{key}  SQL error: {message}")
        elif status == "skipped":
            ctx.logger.warn(
                f"{key}  dry-run not validated (statement type not supported by dry-run)"
            )
    if errors:
        return "error", ""
    return "ok", ""


def summary(logger, command, applied, skipped, errors):
    def n(count, word):
        if word == "error":
            return f"{count} error" if count == 1 else f"{count} errors"
        return f"{count} {word}"

    message = (
        f"psmt {command} completed "
        f"({n(applied, 'applied')}, {n(skipped, 'skipped')}, {n(errors, 'error')})"
    )
    if errors:
        logger.error(message)
    else:
        logger.info(message)


def process_file_content(ctx, path, key):
    from .. import wrapping

    engine = ctx.cfg.engine
    content = path.read_text(encoding="utf-8")
    processed = wrapping.process_file(
        content,
        engine,
        ctx.env,
        strip=ctx.cfg.transaction_strip,
        strip_patterns=ctx.cfg.transaction_strip_patterns,
    )
    if not processed.wrapped:
        ctx.logger.warn(f"{key}  wrapping skipped ({processed.reason})")
    return processed
