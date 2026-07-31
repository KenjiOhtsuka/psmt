import os
import re
import sys

ANSI_RESET = "\x1b[0m"
ANSI_DIM = "\x1b[2m"
ANSI_GREEN = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"
ANSI_RED = "\x1b[31m"

LEVEL_DEBUG = 0
LEVEL_INFO = 1
LEVEL_WARN = 2
LEVEL_ERROR = 3

LEVEL_PREFIX = {
    LEVEL_DEBUG: "[debug]",
    LEVEL_INFO: "[info]",
    LEVEL_WARN: "[warn]",
    LEVEL_ERROR: "[error]",
}

LEVEL_COLOR = {
    LEVEL_DEBUG: ANSI_DIM,
    LEVEL_INFO: ANSI_GREEN,
    LEVEL_WARN: ANSI_YELLOW,
    LEVEL_ERROR: ANSI_RED,
}

_REDACT_PAIRS = re.compile(r"(?i)(password|pwd|clientsecret|secret)\s*=\s*([^;\s\"']+)")

REDACTED = "***"


def redact(text):
    if text is None:
        return None
    return _REDACT_PAIRS.sub(lambda m: m.group(1) + "=" + REDACTED, str(text))


class Logger:
    def __init__(self, verbose=0, no_color=None, stream=None):
        self.verbose = verbose
        self.stream = stream if stream is not None else sys.stdout
        if no_color is None:
            no_color = os.environ.get("NO_COLOR") is not None
        self.use_color = (not no_color) and self.stream.isatty()

    def _emit(self, level, msg):
        prefix = LEVEL_PREFIX[level]
        if self.use_color:
            prefix = LEVEL_COLOR[level] + prefix + ANSI_RESET
        print(prefix, redact(msg), file=self.stream)

    def debug(self, msg, detail=1):
        if self.verbose >= detail:
            self._emit(LEVEL_DEBUG, msg)

    def info(self, msg):
        self._emit(LEVEL_INFO, msg)

    def warn(self, msg):
        self._emit(LEVEL_WARN, msg)

    def error(self, msg):
        self._emit(LEVEL_ERROR, msg)

    def raw(self, msg):
        print(redact(msg), file=self.stream)
