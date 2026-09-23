"""Update both plugin manifests during a Cocogitto release."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = (
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".codex-plugin" / "plugin.json",
)


def main():
    version = sys.argv[1]
    manifests = [(path, json.loads(path.read_text())) for path in MANIFESTS]
    for path, manifest in manifests:
        manifest["version"] = version
        path.write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
