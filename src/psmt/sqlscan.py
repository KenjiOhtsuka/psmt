import re

CTX_CODE = ord("c")
CTX_STRING = ord("s")
CTX_IDENT = ord("i")
CTX_COMMENT = ord("m")
CTX_LINECOMMENT = ord("l")

_DOLLAR_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def classify(text):
    n = len(text)
    kinds = bytearray(b"c") * n
    i = 0
    while i < n:
        ch = text[i]
        if ch == "'":
            backslash = i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_")
            start = i
            i += 1
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                if backslash and text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            for j in range(start, min(i, n)):
                kinds[j] = CTX_STRING
        elif ch == "$":
            m = _DOLLAR_RE.match(text, i)
            if m:
                tag = m.group(0)
                start = i
                i += len(tag)
                while i < n:
                    if text.startswith(tag, i):
                        i += len(tag)
                        break
                    i += 1
                for j in range(start, min(i, n)):
                    kinds[j] = CTX_STRING
            else:
                i += 1
        elif ch == '"':
            start = i
            i += 1
            while i < n:
                if text[i] == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            for j in range(start, min(i, n)):
                kinds[j] = CTX_IDENT
        elif ch == "`":
            start = i
            i += 1
            while i < n:
                if text[i] == "`":
                    if i + 1 < n and text[i + 1] == "`":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            for j in range(start, min(i, n)):
                kinds[j] = CTX_IDENT
        elif ch == "[":
            start = i
            i += 1
            while i < n and text[i] != "]":
                i += 1
            if i < n:
                i += 1
            for j in range(start, min(i, n)):
                kinds[j] = CTX_IDENT
        elif ch == "-" and i + 1 < n and text[i + 1] == "-":
            start = i
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            for j in range(start, min(i, n)):
                kinds[j] = CTX_LINECOMMENT
        elif ch == "#":
            j = i - 1
            while j >= 0 and text[j] != "\n":
                j -= 1
            if all(c in " \t" for c in text[j + 1 : i]):
                start = i
                i += 1
                while i < n and text[i] != "\n":
                    i += 1
                for j in range(start, min(i, n)):
                    kinds[j] = CTX_LINECOMMENT
            else:
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            start = i
            i += 2
            depth = 1
            while i < n and depth:
                if text[i : i + 2] == "/*":
                    depth += 1
                    i += 2
                elif text[i : i + 2] == "*/":
                    depth -= 1
                    i += 2
                else:
                    i += 1
            for j in range(start, min(i, n)):
                kinds[j] = CTX_COMMENT
        else:
            i += 1
    return kinds


def line_starts_in_code(text):
    kinds = classify(text)
    n = len(text)
    starts = []
    i = 0
    while i < n:
        j = i
        while j < n and text[j] in " \t\r":
            j += 1
        starts.append(j < n and kinds[j] == CTX_CODE)
        while i < n and text[i] != "\n":
            i += 1
        if i < n:
            i += 1
    return starts


def line_starts_in_comment(text):
    kinds = classify(text)
    n = len(text)
    starts = []
    i = 0
    while i < n:
        j = i
        while j < n and text[j] in " \t\r":
            j += 1
        starts.append(j < n and kinds[j] == CTX_LINECOMMENT)
        while i < n and text[i] != "\n":
            i += 1
        if i < n:
            i += 1
    return starts


def split_statements(text):
    kinds = classify(text)
    n = len(text)
    start = 0
    out = []
    for i in range(n):
        if kinds[i] == CTX_CODE and text[i] == ";":
            stmt = text[start:i].strip()
            if stmt:
                out.append(stmt)
            start = i + 1
    stmt = text[start:].strip()
    if stmt:
        out.append(stmt)
    return out


def first_code_index(text):
    kinds = classify(text)
    n = len(text)
    i = 0
    while i < n and kinds[i] != CTX_CODE:
        i += 1
    return i


def code_head(text, limit=200):
    kinds = classify(text)
    out = []
    for i, ch in enumerate(text):
        if i >= limit:
            break
        out.append(ch if kinds[i] == CTX_CODE else " ")
    return "".join(out)


def first_words(stmt, count=3):
    i = first_code_index(stmt)
    head = stmt[i : i + 160]
    words = _WORD_RE.findall(head)
    return [w.upper() for w in words[:count]]
