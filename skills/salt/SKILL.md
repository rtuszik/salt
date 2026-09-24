---
name: salt
description: Model-based frustration insights. Classifies every user message with the Laya decision model, so it catches insults, rage, and frustration without swearing, including obfuscated and non-English curses. Auto-detects Claude Code, Codex, and Opencode transcripts and produces an HTML report plus a console summary. Needs uv; the first run downloads ~1.5 GB of model weights. Use when the user says "/salt", "show me the salt", "salt report", "find my curses", "rage report", "frustration insights", or asks who got cursed at most.
---

# Salt: Model-Based Frustration Insights

Scans every available AI agent transcript on disk and asks the Laya model one question about each user message:

| Question   | Type  | Output                                        |
| ---------- | ----- | --------------------------------------------- |
| `severity` | score | 0 (calm) to 3 (furious, insulting or abusive) |

A message is salty when `severity` ≥ `--min-severity` (default 1.55). This default comes from 155
messages labeled by the author (F1 0.82). Your own style may need another value, see [Tuning the
cutoffs](#tuning-the-cutoffs). Extra profanity and "annoyed" questions added no measurable gain, so
the script does not ask them.

Before classification, the script removes pasted lines: code fences, indented blocks, shell prompts,
box-drawing and powerline glyphs, log lines, tables, and bare commands. Only the typed lines are
classified and shown. Messages with no typed lines are skipped.

The target (`agent` or `ambient`) comes from a pronoun and keyword heuristic (English and
German), not from Laya. Laya target questions tested unreliable.

Trigger words come from the salt word list in `saltlib/words.toml` plus the bundled LDNOOBW lists
(28 languages, CC-BY-4.0). Before matching, the script removes Markdown emphasis, collapses
elongations ("fuuuck"), maps leetspeak ("sh1t", "bull$hit"), and resolves censored forms ("f**k",
"ret***"). Phrases count once, not also as their single words. Trigger words supply the badges and
leaderboard, and decide which salty messages count as profane in the report. They do not affect
detection.

The saltiness score (0 to 100) is `100 × sqrt(mean hostility)` over all typed messages, where
hostility is `clamp((severity - 1) / 2, 0, 1)`. It does not depend on `--min-severity`. The console
and the HTML report show it overall and for each agent.

## Tuning the cutoffs

To fit the cutoff to your own messages:

```bash
<skill-dir>/analyze.py --label 200   # label a sample: y = salty, n = not, s = skip, q = quit
<skill-dir>/analyze.py --tune        # search the severity cutoff, print precision/recall and misses
```

`--label` needs an interactive terminal. The `!` prefix in Claude Code does not provide one, so the
user must run it in a separate terminal window. The sample favors messages near the cutoffs. Labels
go to `~/.cache/salt/labels.jsonl`, and later `--label` runs skip messages that are already
labeled. `--tune` prints a suggested `--min-severity` value. The labeled sample is biased toward the
cutoff, so its precision and recall are only useful to compare cutoffs.

## Sources auto-detected

| Agent       | Path                                                                                                                                                        |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | `~/.claude/projects/**/*.jsonl`                                                                                                                             |
| Codex       | `~/.codex/history.jsonl`                                                                                                                                    |
| Opencode    | `~/.local/share/opencode/opencode.db` (sqlite, primary), `~/.local/share/opencode/storage/` (JSON fallback), `~/.local/state/opencode/prompt-history.jsonl` |

## Requirements

- `uv` on `PATH`. The script is a PEP 723 uv script with a committed lockfile (`analyze.py.lock`).
- Tested on macOS with Apple silicon, where Laya runs on MPS automatically. Other platforms are
  untested. On Linux x86_64, PyPI's torch wheel includes CUDA and is about 550 MB.
- About 1.5 GB of disk for the pinned `convaiinnovations/laya` checkpoints (english + multilingual),
  cached by Hugging Face in `~/.cache/huggingface`.

## How to invoke

```bash
<skill-dir>/analyze.py                     # all detected sources (default)
<skill-dir>/analyze.py --only claude       # restrict to one source
<skill-dir>/analyze.py --no-codex          # exclude one source
<skill-dir>/analyze.py --limit 200         # quick test on the first 200 messages
<skill-dir>/analyze.py --min-severity 2.0  # only clear frustration
```

A full scan takes several minutes. Run it in the background and wait for it to finish. Progress and ETA go to stderr.

Classifications are cached in `~/.cache/salt/`, keyed by model revision and question set. Later
runs classify only new messages. Use `--no-cache` to reclassify everything.

The console summary goes to stdout. The HTML report goes to `~/.claude/usage-data/salt-report.html`.

## After running

Echo the console output verbatim, then add the `Report: file://…` line that the script prints. Do
NOT summarize or paraphrase the analyzer output.

## Files

- `analyze.py`: PEP 723 uv entry point. Parses flags and runs the pipeline.
- `analyze.py.lock`: uv lockfile for the script dependencies.
- `saltlib/sources.py`: reads Claude Code, Codex, and Opencode transcripts (sqlite, legacy JSON,
  prompt history).
- `saltlib/paste.py`: strips pasted output so only typed lines are scored.
- `saltlib/scoring.py`: Laya model download, severity scoring, and the score cache.
- `saltlib/heuristics.py`: target classification and trigger-word matching.
- `saltlib/report.py` and `saltlib/report.html`: console summary and HTML report template.
- `saltlib/tuning.py`: the `--label` and `--tune` modes.
- `saltlib/words.toml`: salt's own trigger words and phrases, LDNOOBW exclusions, paste command
  names, and ambient keywords. Edit this file to change the lists.
- `saltlib/ldnoobw/`: LDNOOBW word lists (unmodified, pinned commit) with their license and
  attribution.
