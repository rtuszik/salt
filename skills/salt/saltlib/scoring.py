"""Laya severity scoring with an on-disk cache."""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "salt"
MODEL_REPO = "convaiinnovations/laya"
MODEL_REVISION = "1c5edc17a7acd8701df6fc341c0d179f1c62c982"
CHECKPOINT_FILES = (
    "rl_agent_config.json",
    "model.safetensors",
    "tokenizer/*",
    "encoder/*",
)

QUESTIONS = {
    "severity": {
        "type": "score",
        "instructions": "How frustrated or hostile is the author of `message`?",
        "criteria": [
            "calm or neutral",
            "mildly annoyed",
            "clearly frustrated or rude",
            "furious, insulting or abusive",
        ],
    },
}


def saltiness(severities: list[float]) -> int:
    """Return 0-100 from the square root of mean hostility.

    Hostility spans 0 at severity 1 to 1 at severity 3.
    """
    if not severities:
        return 0
    hostility = sum(min(max((s - 1) / 2, 0.0), 1.0) for s in severities) / len(
        severities
    )
    return round(100 * hostility**0.5)


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_path(questions: dict) -> Path:
    qhash = hashlib.sha256(json.dumps(questions, sort_keys=True).encode()).hexdigest()
    return CACHE_DIR / f"{MODEL_REVISION[:12]}-{qhash[:12]}.jsonl"


def load_jsonl(path: Path) -> dict[str, dict]:
    """Records keyed by their "key" field; later lines win."""
    records: dict[str, dict] = {}
    if not path.exists():
        return records
    with path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            records[rec["key"]] = rec
    return records


def build_router():
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    from huggingface_hub import snapshot_download
    from laya import Router

    patterns = [*CHECKPOINT_FILES, *(f"multilingual/{p}" for p in CHECKPOINT_FILES)]
    print(
        f"Fetching {MODEL_REPO}@{MODEL_REVISION[:12]} (first run downloads ~1.5 GB)…",
        file=sys.stderr,
    )
    model_dir = snapshot_download(
        MODEL_REPO, revision=MODEL_REVISION, allow_patterns=patterns
    )
    router = Router(
        models={"english": model_dir, "multilingual": (model_dir, "multilingual")}
    )
    router.preload(["english", "multilingual"])
    print(
        f"Loaded english + multilingual checkpoints on "
        f"{router.load('english').device}.",
        file=sys.stderr,
    )
    return router


def score_texts(texts: list[str], *, use_cache: bool = True) -> dict[str, dict]:
    """Map each text to {"severity", "model"}; only uncached texts load the model."""
    path = cache_path(QUESTIONS)
    cache = load_jsonl(path) if use_cache else {}
    unique = list(dict.fromkeys(texts))
    pending = [t for t in unique if text_key(t) not in cache]
    print(
        f"{len(unique)} unique texts, {len(unique) - len(pending)} cached, "
        f"{len(pending)} to classify.",
        file=sys.stderr,
    )

    if pending:
        router = build_router()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        with path.open("a") as out:
            for i, text in enumerate(pending, 1):
                res = router.predict({"message": text}, QUESTIONS)
                rec = {
                    "key": text_key(text),
                    "severity": res["answers"]["severity"]["score"],
                    "model": res["routing"]["model"],
                }
                cache[rec["key"]] = rec
                out.write(json.dumps(rec) + "\n")
                if i % 50 == 0 or i == len(pending):
                    out.flush()
                    rate = i / (time.monotonic() - start)
                    print(
                        f"  {i}/{len(pending)}  {rate:.1f} msg/s  "
                        f"ETA {(len(pending) - i) / rate:.0f}s",
                        file=sys.stderr,
                    )
    return {t: cache[text_key(t)] for t in unique}
