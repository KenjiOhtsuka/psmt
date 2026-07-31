import re
from dataclasses import dataclass
from pathlib import Path

VERSION_RE = re.compile(r"^[A-Za-z0-9-]+$")
DESCRIPTION_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DIRECTIONS = ("do", "undo")


@dataclass
class FolderSpec:
    main_version: str
    description: str
    path: Path
    conforming: bool
    reason: str = ""

    @property
    def name(self):
        return self.path.name


@dataclass
class FileSpec:
    sub_version: str
    description: str
    direction: str
    path: Path
    conforming: bool
    reason: str = ""

    @property
    def prefix(self):
        return f"{self.sub_version}_{self.description}"

    @property
    def key(self):
        return (self.main_version, self.sub_version)


@dataclass
class MigrationFile:
    folder: FolderSpec
    file: FileSpec

    @property
    def main_version(self):
        return self.folder.main_version

    @property
    def sub_version(self):
        return self.file.sub_version

    @property
    def key(self):
        return (self.main_version, self.sub_version)

    @property
    def direction(self):
        return self.file.direction

    @property
    def path(self):
        return self.file.path


def is_sql_variant(name):
    return name.lower().endswith(".sql")


def parse_folder(name):
    if "_" not in name:
        return None
    main, description = name.split("_", 1)
    if not main or not description:
        return None
    if not VERSION_RE.match(main):
        return None
    if not DESCRIPTION_RE.match(description):
        return None
    return main, description


def parse_file(name):
    if not name.endswith(".sql"):
        return None
    base = name[: -len(".sql")]
    idx = base.rfind("__")
    if idx == -1:
        return None
    prefix = base[:idx]
    direction = base[idx + 2 :]
    if direction not in DIRECTIONS:
        return None
    if "_" not in prefix:
        return None
    sub_version, description = prefix.split("_", 1)
    if not sub_version or not description:
        return None
    if not VERSION_RE.match(sub_version):
        return None
    if not DESCRIPTION_RE.match(description):
        return None
    return sub_version, description, direction


def classify_folder(path):
    main_desc = parse_folder(path.name)
    if main_desc is None:
        if "_" not in path.name:
            return FolderSpec("", "", path, False, "no underscore separator")
        main, description = path.name.split("_", 1)
        if not main:
            return FolderSpec("", "", path, False, "empty main_version")
        if not description:
            return FolderSpec(main, "", path, False, "empty description")
        if not VERSION_RE.match(main):
            return FolderSpec("", "", path, False, "invalid main_version charset")
        return FolderSpec(main, "", path, False, "invalid description charset")
    return FolderSpec(main_desc[0], main_desc[1], path, True)


def classify_file(folder, path):
    parsed = parse_file(path.name)
    if parsed is None:
        if not is_sql_variant(path.name):
            return None
        reason = _file_reason(path.name)
        return FileSpec("", "", "", path, False, reason)
    return FileSpec(parsed[0], parsed[1], parsed[2], path, True)


def _file_reason(name):
    if not name.endswith(".sql"):
        return "not a lowercase .sql extension"
    base = name[: -len(".sql")]
    if "__" not in base:
        return "no __ direction separator"
    idx = base.rfind("__")
    direction = base[idx + 2 :]
    if direction not in DIRECTIONS:
        return f"invalid direction: {direction}"
    prefix = base[:idx]
    if "_" not in prefix:
        return "no sub_version separator"
    sub_version, description = prefix.split("_", 1)
    if not sub_version:
        return "empty sub_version"
    if not description:
        return "empty description"
    if not VERSION_RE.match(sub_version):
        return "invalid sub_version charset"
    return "invalid description charset"


def scan_folders(migrations_dir):
    folders = []
    if migrations_dir.is_dir():
        for entry in sorted(migrations_dir.iterdir()):
            if entry.is_dir():
                folders.append(classify_folder(entry))
    return folders


def scan_files(folder):
    files = []
    for entry in sorted(folder.path.iterdir()):
        if entry.is_file():
            f = classify_file(folder, entry)
            if f is not None:
                files.append(f)
    return files


def build_index(migrations_dir):
    folders = {}
    non_conforming_folders = []
    for folder in scan_folders(migrations_dir):
        if folder.conforming:
            folders.setdefault(folder.main_version, []).append(folder)
        else:
            non_conforming_folders.append(folder)
    return folders, non_conforming_folders


def find_do_undo(files):
    by_prefix = {}
    for f in files:
        by_prefix.setdefault(f.prefix, {})[f.direction] = f
    return by_prefix


def conforming_folders(migrations_dir):
    folders = [f for f in scan_folders(migrations_dir) if f.conforming]
    folders.sort(key=lambda f: f.main_version)
    return folders


def collect_files(migrations_dir, direction):
    result = []
    for folder in conforming_folders(migrations_dir):
        for f in scan_files(folder):
            if f.conforming and f.direction == direction:
                result.append(MigrationFile(folder, f))
    result.sort(key=lambda m: (m.main_version, m.sub_version))
    return result
