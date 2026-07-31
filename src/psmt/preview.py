import re
from pathlib import Path

from . import tracker, wrapping
from .exceptions import MigrationNotFoundError
from .naming import collect_files


def run_preview(ctx, target, undo=False, no_tracker=False, output_dir=None, raw=False):
    logger = ctx.logger
    engine = ctx.cfg.engine
    direction = "undo" if undo else "do"
    files = collect_files(ctx.migrations_dir, direction)
    matches = [
        f
        for f in files
        if f.main_version == target.main_version and f.sub_version == target.sub_version
    ]
    if not matches:
        raise MigrationNotFoundError(
            f"migration version not found: {target.main_version}:{target.sub_version}"
        )
    migration = matches[0]
    key = f"{migration.main_version}:{migration.sub_version}"
    content = migration.path.read_text(encoding="utf-8")

    if raw:
        text = content
    else:
        processed = wrapping.process_file(
            content,
            engine,
            ctx.env,
            strip=ctx.cfg.transaction_strip,
            strip_patterns=ctx.cfg.transaction_strip_patterns,
        )
        if not processed.wrapped:
            logger.warn(f"{key}  wrapping skipped ({processed.reason})")
        if no_tracker:
            tracker_stmt = None
        elif undo:
            tracker_stmt = tracker.delete_statement(
                migration.main_version, migration.sub_version
            )
        else:
            tracker_stmt = tracker.insert_statement(
                engine, migration.main_version, migration.sub_version
            )
        if processed.wrapped:
            text = wrapping.wrap_content(engine, processed.content, tracker_stmt)
        else:
            text = processed.content
            if tracker_stmt:
                text = (
                    text.rstrip("\n")
                    + "\n\n-- psmt: _migration tracking\n"
                    + tracker_stmt
                )

    if output_dir:
        env_dir = re.sub(r"[./]", "_", ctx.env)
        folder_name = migration.path.parent.name
        out_path = Path(output_dir) / env_dir / folder_name / migration.path.name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        logger.info(f"wrote 1 file(s) to {output_dir}")
    else:
        logger.raw(text)
    return 0
