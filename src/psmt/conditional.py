import re

from . import sqlscan
from .exceptions import ConditionalError

_IF_RE = re.compile(r"^\s*--\s*@if\s+(.*)$")
_ELSE_RE = re.compile(r"^\s*--\s*@else\s*$")
_ENDIF_RE = re.compile(r"^\s*--\s*@endif\s*$")
_NOT_RE = re.compile(r"^not\s*\((.*)\)\s*$", re.IGNORECASE)


def _split_list(text):
    return [part.strip() for part in text.split(",") if part.strip()]


def _matches(condition, env):
    m = _NOT_RE.match(condition.strip())
    if m:
        return env not in _split_list(m.group(1))
    return env in _split_list(condition.strip())


def process_conditionals(text, env):
    lines = text.split("\n")
    starts = sqlscan.line_starts_in_comment(text)
    stack = []
    out = []
    for idx, line in enumerate(lines):
        in_code = starts[idx] if idx < len(starts) else False
        trimmed = line.lstrip()
        if in_code:
            m_if = _IF_RE.match(line)
            m_else = _ELSE_RE.match(line)
            m_endif = _ENDIF_RE.match(line)
            if m_if:
                included = _matches(m_if.group(1), env)
                stack.append({"included": included, "else_seen": False})
                continue
            if m_else:
                if not stack:
                    raise ConditionalError("unexpected -- @else without -- @if")
                if stack[-1]["else_seen"]:
                    raise ConditionalError("duplicate -- @else in one block")
                stack[-1]["included"] = not stack[-1]["included"]
                stack[-1]["else_seen"] = True
                continue
            if m_endif:
                if not stack:
                    raise ConditionalError("unexpected -- @endif without -- @if")
                stack.pop()
                continue
        if all(frame["included"] for frame in stack):
            out.append(line)
    if stack:
        raise ConditionalError("unclosed -- @if block")
    return "\n".join(out)
