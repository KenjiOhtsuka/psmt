import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .exceptions import OperationalError, UsageError

SAFE_SUMMARY_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_INVALID_RE = re.compile(r"[^A-Za-z0-9._-]")


def utc_timestamp():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H%M%S%f")[:17]


def sanitize_summary(summary):
    value = _INVALID_RE.sub("_", summary)
    value = value.replace("/", "_").replace("\\", "_")
    value = value.replace("..", "_")
    return value


def new_folder_name(timestamp, summary):
    return f"{timestamp}_{summary}"


def find_collision_free_name(migrations_dir, summary, now_fn=None):
    if now_fn is None:
        now_fn = utc_timestamp
    existing = [e.name for e in migrations_dir.iterdir() if e.is_dir()]
    while True:
        timestamp = now_fn()
        name = new_folder_name(timestamp, summary)
        if name in existing:
            continue
        if any(e.split("_", 1)[0] == timestamp for e in existing):
            continue
        return name, timestamp


def run_generate(migrations_dir, summary=None, interactive=sys.stdin.isatty()):
    if summary is None:
        if not interactive:
            raise OperationalError("interactive input unavailable; pass --summary")
        summary = input("Summary: ")
    sanitized = sanitize_summary(summary)
    if not sanitized:
        raise UsageError(f"invalid summary: {summary}")
    name, _timestamp = find_collision_free_name(migrations_dir, sanitized)
    folder = migrations_dir / name
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "01_migrate__do.sql").write_text("", encoding="utf-8")
    (folder / "01_migrate__undo.sql").write_text("", encoding="utf-8")
    return folder
