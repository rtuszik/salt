"""Strip pasted terminal output, logs, and code so only typed lines remain."""

import re

from . import WORDS

COMMANDS = set(WORDS["paste"]["commands"])
URL_RE = re.compile(r"https?://\S+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
# Box drawing, powerline/nerd-font glyphs, and their mac-roman mojibake.
GLYPH_RE = re.compile(
    r"[\u2500-\u25ff\u2713-\u2718\u276f\u279c\ue000-\uf8ff\U000f0000-\U0010ffff]"
    r"|\u201aî|\u201aï|\u201aú|\u201añ|\u201aóè|ÓÇ|Û∞|Û±|Ôê"
)
PROMPT_RE = re.compile(r"^\s*(?:\S+@\S+:\S*\s*[$#]|[$#>] |PS [A-Z]:\\)")
LOG_RE = re.compile(
    r"^\s*(?:(?:ERROR|WARN|WARNING|INFO|DEBUG|FATA|FATAL|TRACE)\b"
    r"|\d{4}[-/]\d{2}[-/]\d{2}|\[\d"
    r"|Traceback|File \"|at \S+\()"
    r"|^\s*</?[a-zA-Z][^>]*>|^[\w./-]+: [\w./ -]+: "
)
TABLE_RE = re.compile(r"\S {2,}\S.* {2,}\S")
PROSE_RE = re.compile(
    r"\b(?:i|me|my|you|your|why|what|how|it|is|are|was|for|not|doesn't|don't|fails?)\b",
    re.IGNORECASE,
)


def is_pasted_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if (
        GLYPH_RE.search(line)
        or PROMPT_RE.match(line)
        or LOG_RE.match(line)
        or TABLE_RE.search(stripped)
    ):
        return True
    if line[:1] in (" ", "\t"):
        return True
    tokens = stripped.split()
    if tokens[0] in COMMANDS and len(tokens) > 1 and not PROSE_RE.search(stripped):
        return True
    prose = sum(c.isalpha() or c.isspace() for c in stripped)
    return len(stripped) >= 20 and prose / len(stripped) < 0.75


def typed_text(content: str) -> str:
    kept, in_fence = [], False
    for raw in content.splitlines():
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        line = URL_RE.sub("", raw).rstrip()
        if not in_fence and not is_pasted_line(line):
            kept.append(line.strip())
    return "\n".join(kept)
