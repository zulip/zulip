"""Read/write puppet/zulip/files/dependencies.json.

Each entry is a dict with consumer fields (read by Puppet) and an
`_updater` subtree describing how to refresh the entry from upstream.
We round-trip with a stable four-space indent and trailing newline,
matching prettier's JSON defaults so updates produce minimal diffs
and the file stays lint-clean.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TOOLS_LIB = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOLS_LIB.parent.parent
DEPS_PATH = REPO_ROOT / "puppet" / "zulip" / "files" / "dependencies.json"

Entry = dict[str, Any]
Deps = dict[str, Entry]


def load(path: Path | None = None) -> Deps:
    with (path or DEPS_PATH).open() as f:
        return json.load(f)


def dump(deps: Deps, path: Path | None = None) -> None:
    (path or DEPS_PATH).write_text(serialize(deps))


def serialize(deps: Deps) -> str:
    # 4-space indent keeps the file prettier-clean; the Zulip lint
    # pipeline runs prettier on .json files and rejects 2-space JSON.
    return json.dumps(deps, indent=4) + "\n"
