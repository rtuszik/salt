"""Report-only heuristics: who the salt targets, and which trigger words it uses."""

import re

from . import PACKAGE_DIR, WORDS

LDNOOBW_DIR = PACKAGE_DIR / "ldnoobw"
NO_SPACE_LANGS = {"ja", "ko", "th", "zh"}
LEET = str.maketrans("013457@$!|", "oieastasii")
TOKEN_RE = re.compile(r"[\w@$*!|']+")
RUN_RE = re.compile(r"(.)\1{2,}")
CENSORED_RE = re.compile(r"[a-z]+\*+[a-z]+|[a-z]{2,}\*{3,}")
EMPHASIS_RE = re.compile(r"(\*{1,2})(?=[^\s*])(.+?)(?<=[^\s*])\1")


def load_triggers() -> tuple[set[str], set[tuple[str, ...]], set[str]]:
    """Hand list plus LDNOOBW, minus exclusions.

    Returns (words, phrases, no-space substrings).
    """
    exclude = set(WORDS["triggers"]["exclude"])
    entries = set(WORDS["triggers"]["words"]) | set(WORDS["triggers"]["phrases"])
    substrings = set()
    for path in LDNOOBW_DIR.iterdir():
        if path.name == "LICENSE":
            continue
        for line in path.read_text().splitlines():
            entry = line.strip().lower()
            if not entry or entry in exclude:
                continue
            if path.name in NO_SPACE_LANGS and not entry.isascii():
                substrings.add(entry)
            else:
                entries.add(entry)
    words = {e for e in entries if " " not in e}
    phrases = {tuple(e.split()) for e in entries if " " in e}
    return words, phrases, substrings


TRIGGER_WORDS, TRIGGER_PHRASES, TRIGGER_SUBSTRINGS = load_triggers()
PHRASE_LENGTHS = sorted({len(p) for p in TRIGGER_PHRASES}, reverse=True)
WORDS_BY_LENGTH: dict[int, list[str]] = {}
for _w in sorted(TRIGGER_WORDS, key=lambda w: (w not in WORDS["triggers"]["words"], w)):
    WORDS_BY_LENGTH.setdefault(len(_w), []).append(_w)

AMBIENT_KEYWORDS = WORDS["target"]["ambient"]
SELF_PATTERNS = [
    r"\bturns out i(?:'?m| am)\b",
    (
        r"\bi(?:'?m| am)\s+(?:an?\s+|so\s+|such\s+(?:an?\s+)?|the\s+"
        r"|being\s+(?:an?\s+|so\s+)?|actually\s+|kinda\s+|kind of\s+|a bit\s+)?"
        r"(?:retard|retarded|stupid|dumb|idiot|moron|braindead|fool|loser|garbage|trash)\b"
    ),
    (
        r"\bi was (?:being|so|such)\s+(?:an?\s+)?"
        r"(?:retarded|stupid|dumb|an idiot|a moron|a fool)\b"
    ),
    r"\bmy (?:bad|fault|mistake)\b",
]
AGENT_PRONOUN_RE = re.compile(
    r"\byou(\b|r\b|'re\b|re\b|'ve\b|ve\b)|\b(?:du|dich|dein|deine|deinen|deinem|deiner)\b",
    re.IGNORECASE,
)


def classify_target(text: str) -> str:
    # Laya target questions tested unreliable; pronoun heuristic instead.
    low = text.lower()
    addresses_agent = bool(AGENT_PRONOUN_RE.search(text))
    if not addresses_agent and any(re.search(p, low) for p in SELF_PATTERNS):
        return "self"
    if not addresses_agent and any(k in low for k in AMBIENT_KEYWORDS):
        return "ambient"
    return "agent"


def normalize(token: str) -> str:
    """Canonical trigger word for a token, else its de-elongated, de-leeted form."""
    token = token.strip("'!|").lower()
    variants = [token]
    if any(c.isdigit() or c in "@$!|" for c in token) and any(
        c.isalpha() for c in token
    ):
        variants.append(token.translate(LEET))
    for v in list(variants):
        if RUN_RE.search(v):
            variants += [RUN_RE.sub(r"\1", v), RUN_RE.sub(r"\1\1", v)]
    for v in variants:
        if v in TRIGGER_WORDS:
            return v
    if CENSORED_RE.fullmatch(token):
        pattern = re.compile(re.escape(token).replace(r"\*", "[a-z]"))
        for word in WORDS_BY_LENGTH.get(len(token), []):
            if pattern.fullmatch(word):
                return word
        return token if token.count("*") >= 2 else variants[-1]
    return variants[-1]


def find_triggers(text: str) -> list[str]:
    """Canonical trigger words and phrases, each span counted once."""
    tokens = [normalize(t) for t in TOKEN_RE.findall(EMPHASIS_RE.sub(r"\2", text))]
    hits, i = [], 0
    while i < len(tokens):
        for n in PHRASE_LENGTHS:
            if tuple(tokens[i : i + n]) in TRIGGER_PHRASES:
                hits.append(" ".join(tokens[i : i + n]))
                i += n
                break
        else:
            if tokens[i] in TRIGGER_WORDS or (
                CENSORED_RE.fullmatch(tokens[i]) and "**" in tokens[i]
            ):
                hits.append(tokens[i])
            i += 1
    low = text.lower()
    found = [s for s in TRIGGER_SUBSTRINGS if s in low]
    hits += [s for s in found if not any(s != t and s in t for t in found)]
    return hits
