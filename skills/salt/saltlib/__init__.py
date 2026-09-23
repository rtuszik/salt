"""Salt internals: transcript sources, paste stripping, scoring, report, tuning."""

from pathlib import Path

import tomllib

PACKAGE_DIR = Path(__file__).resolve().parent
WORDS = tomllib.loads((PACKAGE_DIR / "words.toml").read_text())
