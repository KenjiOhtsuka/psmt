from ..naming import collect_files


def run_versions(ctx):
    driver = ctx.driver
    conn = driver.connect(ctx.cfg)
    try:
        applied = driver.fetch_applied(conn)
    finally:
        driver.close(conn)
    disk = {(f.main_version, f.sub_version) for f in collect_files(ctx.migrations_dir, "do")}
    for main, sub in sorted(disk | applied):
        if (main, sub) in applied and (main, sub) in disk:
            status = "migrated"
        elif (main, sub) in applied:
            status = "migrated (only in db)"
        else:
            status = "not migrated (only in file)"
        ctx.logger.raw(f"{main}:{sub}  {status}")
