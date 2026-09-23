# salt

salt reads the messages you typed to Claude Code, Codex, and Opencode.
It scores each one on-device with the [Laya](https://pypi.org/project/laya/) decision
model and writes a report of some of your best zingers.

## How it works

1. Reads user messages from every agent transcript it finds on disk.
2. Strips pasted content.
3. Asks Laya one question for each message: "How frustrated or hostile is the
   author?" The answer is a score from 0 (calm) to 3 (furious, insulting or
   abusive). A message is salty at 1.55 or higher.
4. Adds heuristics for the report: the target (agent, self, or ambient) and
   trigger-word badges. Trigger words come from salt's own list plus the
   LDNOOBW lists in 28 languages. Matching handles elongations, leetspeak,
   and censored forms. These heuristics do not affect detection.
5. Prints a console summary and writes an HTML report.

| Agent       | Path                                                                                                       |
| ----------- | ---------------------------------------------------------------------------------------------------------- |
| Claude Code | `~/.claude/projects/**/*.jsonl`                                                                            |
| Codex       | `~/.codex/history.jsonl`                                                                                   |
| Opencode    | `~/.local/share/opencode/opencode.db`, `~/.local/share/opencode/storage/`, `~/.local/state/opencode/prompt-history.jsonl` |

The model runs locally. The only network traffic
is the download of Python packages from PyPI and the model
weights from Hugging Face on the first run.

The report quotes your messages. Read it before you share it.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- About 1.5 GB of disk for the model weights (english and multilingual Laya
  checkpoints), cached in `~/.cache/huggingface`
- Tested on macOS with Apple silicon. Other platforms are untested.

## Install

### Claude Code

```text
/plugin marketplace add rtuszik/salt
/plugin install salt@salt
```

Then ask Claude for a salt report.

### Codex

```sh
codex plugin marketplace add /path/to/salt
codex plugin add salt@salt
```

### Standalone

The script is a [PEP 723](https://peps.python.org/pep-0723/) uv script with a
committed lockfile. It runs without the plugin:

```sh
./skills/salt/analyze.py
```

## Usage

```sh
analyze.py                     # all detected sources
analyze.py --only claude       # one source
analyze.py --no-codex          # exclude one source
analyze.py --min-severity 2.0  # only clear frustration
analyze.py --limit 200         # quick test on the first 200 messages
analyze.py --no-cache          # score everything again
```

The first run downloads the model and scores every message. On an M2 Max
this is about 30 messages per second. Later runs score only new messages.

## Tuning

The default cutoff of 1.55 comes from 155 messages labeled by the author.
To fit it to your own messages, run these commands in a regular terminal:

```sh
analyze.py --label 200   # y = salty, n = not salty, s = skip, q = quit
analyze.py --tune        # prints precision, recall, misses, and a suggested cutoff
```

The label sample favors messages near the cutoff. Its precision and recall
are useful to compare cutoffs, but they are not estimates for your full
history.

## Known limits

- Some short, calm commands score above 1.55, for example "Delete the failing
  sandboxes".
- Dry or sarcastic messages such as "Bruh" score low.
- The target heuristic knows only English and German pronouns.
- Laya 0.3.5 and the model revision are pinned. Newer versions can give
  different scores.

## License

Apache-2.0. See [LICENSE](LICENSE).

The Laya package and model weights by Convai Innovations are also
Apache-2.0.

The word lists in `skills/salt/saltlib/ldnoobw/` are the
[List of Dirty, Naughty, Obscene, and Otherwise Bad Words](https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words)
by Shutterstock and contributors, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See
[their README](skills/salt/saltlib/ldnoobw/README.md) for the pinned commit
and changes.
