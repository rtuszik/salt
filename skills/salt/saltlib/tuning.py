"""Interactive labeling and severity-cutoff search against your own labels."""

import json
import random
import sys

from .report import truncate
from .scoring import CACHE_DIR, load_jsonl, score_texts, text_key
from .sources import load_messages

LABELS_FILE = CACHE_DIR / "labels.jsonl"


def read_key() -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def label(include: set[str], min_severity: float, n: int):
    if not sys.stdin.isatty():
        sys.exit(
            "--label needs an interactive terminal. "
            "Run it in a separate terminal window."
        )
    messages, _ = load_messages(include, None)
    scores = score_texts([m[2] for m in messages if m[2]])
    done = load_jsonl(LABELS_FILE)
    pool = [t for t in scores if text_key(t) not in done]

    boundary = {t for t in pool if abs(scores[t]["severity"] - min_severity) <= 0.35}
    salty = {
        t for t in pool if t not in boundary and scores[t]["severity"] >= min_severity
    }
    rest = [t for t in pool if t not in boundary | salty]
    rng = random.Random()  # noqa: S311 - Sampling labels, not secrets.
    picks: list[str] = []
    for bucket, share in ((sorted(boundary), 0.5), (sorted(salty), 0.25), (rest, 0.25)):
        picks += rng.sample(bucket, min(len(bucket), round(n * share)))
    rng.shuffle(picks)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"{len(done)} labels so far. Salty = frustration, anger, "
        f"insults or swearing at anything.\n"
    )
    count = 0
    with LABELS_FILE.open("a") as out:
        for i, text in enumerate(picks, 1):
            print(f"\n[{i}/{len(picks)}] " + "-" * 60)
            print(text if len(text) <= 800 else text[:800] + " …")
            print(
                "\n  [y] salty   [n] not salty   [s] skip   [q] quit  ",
                end="",
                flush=True,
            )
            key = ""
            while key not in ("y", "n", "s", "q", "\x03"):
                key = read_key()
            print(key)
            if key in ("q", "\x03"):
                break
            if key == "s":
                continue
            out.write(
                json.dumps(
                    {"key": text_key(text), "text": text, "label": int(key == "y")}
                )
                + "\n"
            )
            out.flush()
            count += 1
    print(f"\nSaved {count} labels to {LABELS_FILE}. Total: {len(done) + count}.")


def frange(start: float, stop: float, step: float) -> list[float]:
    return [round(start + i * step, 3) for i in range(round((stop - start) / step) + 1)]


def evaluate(
    min_severity: float, rows: list[tuple[dict, int]]
) -> tuple[float, float, float]:
    tp = sum(1 for sc, y in rows if y and sc["severity"] >= min_severity)
    fp = sum(1 for sc, y in rows if not y and sc["severity"] >= min_severity)
    fn = sum(1 for sc, y in rows if y and sc["severity"] < min_severity)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def tune(current: float):
    labels = list(load_jsonl(LABELS_FILE).values())
    if not labels:
        sys.exit(f"No labels in {LABELS_FILE}. Run --label first.")
    texts = [rec["text"] for rec in labels]
    scores = score_texts(texts)
    rows = [(scores[rec["text"]], rec["label"]) for rec in labels]
    positives = sum(y for _, y in rows)
    print(
        f"\n{len(rows)} labels, {positives} salty, {len(rows) - positives} not salty."
    )
    if len(rows) < 100:
        print("Fewer than 100 labels: treat the result as a rough guide.")

    best = max(
        frange(0.5, 2.8, 0.05),
        key=lambda v: (evaluate(v, rows)[2], evaluate(v, rows)[0]),
    )

    def show(name: str, value: float):
        p, r, f1 = evaluate(value, rows)
        print(
            f"{name:8} min-severity={value:.2f}  precision={p:.2f} "
            f"recall={r:.2f} F1={f1:.2f}"
        )

    print()
    show("current", current)
    show("best", best)
    for title, want in (("False positives", 0), ("False negatives", 1)):
        misses = [
            (sc, t)
            for (sc, y), t in zip(rows, texts, strict=True)
            if y == want and (sc["severity"] >= best) != bool(want)
        ]
        print(f"\n{title} under best ({len(misses)}):")
        for sc, t in misses[:10]:
            print(f"  s={sc['severity']:.2f} | {truncate(t, 100)}")
    print(f"\nSuggested flag: --min-severity {best}")
