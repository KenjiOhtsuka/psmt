import re

from . import sqlscan
from .conditional import process_conditionals

NOWRAP_RE = re.compile(r"^\s*--\s*@nowrap\b")

WRAP_PREFIX = {
    "postgresql": "START TRANSACTION;",
    "mysql": "START TRANSACTION;",
    "sqlite": "BEGIN;",
    "mssql": "SET XACT_ABORT ON;\nBEGIN TRANSACTION;",
    "oracle": None,
    "db2": None,
}

WRAP_SUFFIX = {
    "postgresql": "COMMIT;",
    "mysql": "COMMIT;",
    "sqlite": "COMMIT;",
    "mssql": "COMMIT TRANSACTION;",
    "oracle": "COMMIT;",
    "db2": "COMMIT;",
}

BEGIN_BARE_OK_RE = r"^\s*BEGIN(?:\s+TRAN(SACTION)?|\s+WORK)?\s*;?\s*$"
BEGIN_NEEDS_ARG_RE = r"^\s*BEGIN\s+(?:TRAN(SACTION)?|WORK)\s*;?\s*$"
START_TRANSACTION_RE = r"^\s*START\s+TRAN(SACTION)?\s*;?\s*$"
COMMIT_ROLLBACK_RE = r"^\s*(?:COMMIT|ROLLBACK)(?:\s+TRAN(SACTION)?|\s+WORK)?\s*;?\s*$"
END_TRANSACTION_RE = r"^\s*END\s+(?:TRAN(SACTION)?|WORK)\s*;?\s*$"
XACT_ABORT_RE = r"^\s*SET\s+XACT_ABORT\s+(ON|OFF)\s*;?\s*$"

ORACLE_DDL_WORDS = {
    "ALTER",
    "ANALYZE",
    "AUDIT",
    "COMMENT",
    "CREATE",
    "DROP",
    "FLASHBACK",
    "GRANT",
    "NOAUDIT",
    "PURGE",
    "RENAME",
    "REVOKE",
    "TRUNCATE",
}

NON_TRANSACTIONAL_PATTERNS = {
    "mssql": [
        r"\b(?:CREATE|ALTER|DROP)\s+DATABASE\b",
        r"\b(?:CREATE|ALTER|DROP)\s+FULLTEXT\s+(?:INDEX|CATALOG)\b",
        r"\bRECONFIGURE\b",
        r"\b(?:CREATE|ALTER)\s+TRIGGER\b",
        r"\b(?:CREATE|ALTER)\s+VIEW\b",
        r"\b(?:CREATE|ALTER)\s+FUNCTION\b",
        r"\b(?:CREATE|ALTER)\s+PROCEDURE\b",
    ],
    "postgresql": [
        r"\bCREATE(?:\s+UNIQUE)?\s+INDEX\s+CONCURRENTLY\b",
        r"\bDROP\s+INDEX\s+CONCURRENTLY\b",
        r"\bREINDEX\s+\S*\s*CONCURRENTLY\b",
        r"\bVACUUM\b",
        r"\b(?:CREATE|DROP)\s+DATABASE\b",
        r"\b(?:CREATE|DROP)\s+TABLESPACE\b",
        r"\bALTER\s+SYSTEM\b",
        r"\b(?:CREATE|DROP)\s+SUBSCRIPTION\b",
        r"\bCLUSTER\b",
    ],
    "db2": [
        r"\b(?:CREATE|DROP)\s+DATABASE\b",
        r"\bREORG\b",
        r"\bRUNSTATS\b",
    ],
}


def default_strip_patterns(engine):
    patterns = [START_TRANSACTION_RE, COMMIT_ROLLBACK_RE, XACT_ABORT_RE]
    if engine in ("sqlite", "postgresql"):
        patterns.insert(0, BEGIN_BARE_OK_RE)
    elif engine in ("mssql", "oracle", "mysql"):
        patterns.insert(0, BEGIN_NEEDS_ARG_RE)
    if engine in ("sqlite", "postgresql"):
        patterns.append(END_TRANSACTION_RE)
    return patterns


def detect_non_transactional(engine, content):
    statements = sqlscan.split_statements(content)
    if engine == "oracle":
        for stmt in statements:
            words = sqlscan.first_words(stmt, 1)
            if words and words[0] in ORACLE_DDL_WORDS:
                return True
        return False
    patterns = NON_TRANSACTIONAL_PATTERNS.get(engine, [])
    if not patterns:
        return False
    for stmt in statements:
        head = sqlscan.code_head(stmt)
        if any(re.search(p, head, re.IGNORECASE) for p in patterns):
            return True
    return False


def strip_transaction_controls(content, engine, custom_patterns=None):
    if custom_patterns:
        patterns = list(custom_patterns)
    else:
        patterns = default_strip_patterns(engine)
    if not patterns:
        return content
    starts = sqlscan.line_starts_in_code(content)
    lines = content.split("\n")
    out = []
    for idx, line in enumerate(lines):
        if idx < len(starts) and starts[idx]:
            for pattern in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    line = ""
                    break
        out.append(line)
    return "\n".join(out)


def wrap_content(engine, content, tracker_stmt=None):
    prefix = WRAP_PREFIX.get(engine)
    suffix = WRAP_SUFFIX[engine]
    text = content
    if tracker_stmt:
        text = text.rstrip("\n") + "\n\n-- psmt: _migration tracking\n" + tracker_stmt
    if prefix is not None:
        return prefix + "\n\n" + text + "\n\n" + suffix
    return text + "\n\n" + suffix


def process_file(content, engine, env, strip=False, strip_patterns=None):
    content = process_conditionals(content, env)
    first_line = content.split("\n", 1)[0]
    if NOWRAP_RE.match(first_line):
        return ProcessedFile(content, wrapped=False, reason="@nowrap")
    if detect_non_transactional(engine, content):
        return ProcessedFile(content, wrapped=False, reason="non-transactional statement detected")
    if strip:
        content = strip_transaction_controls(content, engine, strip_patterns)
    return ProcessedFile(content, wrapped=True, reason=None)


class ProcessedFile:
    def __init__(self, content, wrapped, reason=None):
        self.content = content
        self.wrapped = wrapped
        self.reason = reason
