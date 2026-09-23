"""Read user-typed messages from Claude Code, Codex, and Opencode."""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .paste import typed_text

HOME = Path.home()
PROJECTS_DIR = HOME / ".claude" / "projects"
CODEX_HISTORY = HOME / ".codex" / "history.jsonl"
OPENCODE_DB = HOME / ".local" / "share" / "opencode" / "opencode.db"
OPENCODE_MSG_DIR = HOME / ".local" / "share" / "opencode" / "storage" / "message"
OPENCODE_PART_DIR = HOME / ".local" / "share" / "opencode" / "storage" / "part"
OPENCODE_PROMPT_HISTORY = (
    HOME / ".local" / "state" / "opencode" / "prompt-history.jsonl"
)

SOURCES = ("claude", "codex", "opencode")
COMMAND_TAG_RE = re.compile(
    r"<(command-name|command-message|command-args|local-command-stdout|local-command-stderr)>[^<]*</\1>"
)


def detect_sources() -> dict[str, bool]:
    return {
        "claude": PROJECTS_DIR.exists() and any(PROJECTS_DIR.rglob("*.jsonl")),
        "codex": CODEX_HISTORY.exists(),
        "opencode": OPENCODE_DB.exists()
        or OPENCODE_MSG_DIR.exists()
        or OPENCODE_PROMPT_HISTORY.exists(),
    }


def looks_like_tool_output(text: str) -> bool:
    if len(text) > 4000 and text.count("\n") > 50:
        return True
    if sum(text.count(m) for m in ("✅", "⚠️", "❌", "✗", "✓")) >= 3:
        return True
    return (
        "==============================" in text
        or "------------------------------" in text
    )


def looks_like_skill_prompt(text: str) -> bool:
    head = text[:200].lstrip()
    if head.startswith("You are "):
        return True
    return head.startswith("# ") and "\n## " in text and len(text) > 1500


def epoch_to_iso(value, divisor: int = 1):
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / divisor).astimezone().isoformat()
    except (OSError, ValueError):
        return None


def parse_ts(ts):
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def iter_claude_messages():
    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        project = jsonl.parent.name
        try:
            with jsonl.open(errors="replace") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = rec.get("message")
                    if not isinstance(msg, dict) or msg.get("role") != "user":
                        continue
                    content = msg.get("content")
                    if not isinstance(content, str):
                        continue
                    cleaned = COMMAND_TAG_RE.sub(" ", content).strip()
                    if not cleaned or looks_like_tool_output(cleaned):
                        continue
                    yield "claude", project, cleaned, rec.get("timestamp")
        except OSError:
            continue


def iter_codex_messages():
    if not CODEX_HISTORY.exists():
        return
    with CODEX_HISTORY.open(errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = rec.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            cleaned = text.strip()
            if looks_like_tool_output(cleaned):
                continue
            yield "codex", "codex", cleaned, epoch_to_iso(rec.get("ts"))


def _iter_opencode_db():
    if OPENCODE_DB.exists():
        try:
            con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True)
            cur = con.execute(
                """
                SELECT json_extract(p.data,'$.text'), m.time_created
                FROM part p
                JOIN message m ON p.message_id = m.id
                WHERE json_extract(m.data,'$.role') = 'user'
                  AND json_extract(p.data,'$.type') = 'text'
                """
            )
            for text, ts_ms in cur:
                yield text, epoch_to_iso(ts_ms, 1000)
            con.close()
        except sqlite3.Error:
            pass


def _iter_opencode_legacy():
    if OPENCODE_MSG_DIR.exists():
        for msg_file in OPENCODE_MSG_DIR.rglob("msg_*.json"):
            try:
                with msg_file.open(errors="replace") as f:
                    msg = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            msg_id = msg.get("id")
            if msg.get("role") != "user" or not msg_id:
                continue
            ts = epoch_to_iso((msg.get("time") or {}).get("created"), 1000)
            part_dir = OPENCODE_PART_DIR / msg_id
            if not part_dir.exists():
                continue
            for prt_file in part_dir.glob("prt_*.json"):
                try:
                    with prt_file.open(errors="replace") as f:
                        prt = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue
                if prt.get("type") != "text":
                    continue
                yield prt.get("text"), ts


def _iter_opencode_history():
    if OPENCODE_PROMPT_HISTORY.exists():
        with OPENCODE_PROMPT_HISTORY.open(errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield rec.get("input"), None


def iter_opencode_messages():
    """Sqlite first, then legacy JSON storage, then prompt history; deduplicated."""
    seen: set[str] = set()
    for reader in (_iter_opencode_db, _iter_opencode_legacy, _iter_opencode_history):
        for text, ts in reader():
            if not isinstance(text, str):
                continue
            cleaned = text.strip()
            if not cleaned or cleaned in seen:
                continue
            if looks_like_tool_output(cleaned) or looks_like_skill_prompt(cleaned):
                continue
            seen.add(cleaned)
            yield "opencode", "opencode", cleaned, ts


def iter_user_messages(include: set[str]):
    if "claude" in include:
        yield from iter_claude_messages()
    if "codex" in include:
        yield from iter_codex_messages()
    if "opencode" in include:
        yield from iter_opencode_messages()


def load_messages(include: set[str], limit: int | None):
    """Return ([(source, project, typed_text, ts)], total_count)."""
    messages = list(iter_user_messages(include))
    if limit:
        messages = messages[:limit]
    return [
        (src, proj, typed_text(content), ts) for src, proj, content, ts in messages
    ], len(messages)
