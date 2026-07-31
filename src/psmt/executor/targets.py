import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ..exceptions import UsageError

VERSION_PART_RE = re.compile(r"^[A-Za-z0-9-]+$")
STEPS_RE = re.compile(r"^[0-9]+$")


@dataclass
class VersionTarget:
    main_version: str
    sub_version: str = None


def parse_version_list(value):
    if value == "all":
        return None
    targets = []
    for element in value.split(","):
        element = element.strip()
        if not element:
            raise UsageError(f"invalid --version value: {value}")
        if ":" in element:
            main, sub = element.split(":", 1)
            if not main or not sub or not VERSION_PART_RE.match(main) or not VERSION_PART_RE.match(sub):
                raise UsageError(f"invalid --version value: {element}")
            targets.append(VersionTarget(main, sub))
        else:
            if not VERSION_PART_RE.match(element):
                raise UsageError(f"invalid --version value: {element}")
            targets.append(VersionTarget(element))
    return targets


def parse_steps(value):
    if value == "all":
        return None
    if not STEPS_RE.match(value or "") or int(value) <= 0:
        raise UsageError(f"invalid --steps value: {value}")
    return int(value)


def parse_preview_version(value):
    if ":" not in value:
        raise UsageError(f"invalid --version value: {value}")
    main, sub = value.split(":", 1)
    if not main or not sub or not VERSION_PART_RE.match(main) or not VERSION_PART_RE.match(sub):
        raise UsageError(f"invalid --version value: {value}")
    return VersionTarget(main, sub)


def utc_now_string():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
