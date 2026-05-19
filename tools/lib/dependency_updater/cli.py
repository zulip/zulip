"""CLI for tools/update-dependency-versions.

Reads puppet/zulip/files/dependencies.json, resolves the latest
version and sha256(s) for each requested package via its configured
provider, and writes the file back (or prints a diff / exits non-zero,
depending on flags).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import os
import sys
from dataclasses import dataclass

import requests

from . import config, providers


@dataclass
class Result:
    name: str
    release: providers.LatestRelease | None
    error: Exception | None


def _apply(entry: config.Entry, release: providers.LatestRelease) -> config.Entry:
    new = dict(entry)
    new["version"] = release.version
    new["sha256"] = release.sha256
    # Keep consumer fields ahead of _updater, as they were.
    updater = new.pop("_updater", None)
    if updater is not None:
        new["_updater"] = updater
    return new


def _fetch_one(name: str, entry: config.Entry) -> Result:
    # One session per call keeps requests.Session (not fully thread-safe)
    # out of the shared-across-threads role.  We make at most a handful of
    # requests per entry so the lost connection pooling is negligible.
    with requests.Session() as session:
        try:
            return Result(
                name=name,
                release=providers.fetch_latest(session, name, entry),
                error=None,
            )
        except Exception as e:
            return Result(name=name, release=None, error=e)


def _render_diff(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="dependencies.json (current)",
            tofile="dependencies.json (updated)",
        )
    )


def _positive_int(raw: str) -> int:
    n = int(raw)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {n}")
    return n


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Update puppet/zulip/files/dependencies.json in place by "
            "re-resolving each package's latest version and sha256 from "
            "its upstream. Set GITHUB_TOKEN in the environment to avoid "
            "the 60-req/hr anonymous GitHub rate limit.  If some packages "
            "fail to resolve but others succeed, the file is written with "
            "the successful updates and the CLI exits non-zero."
        ),
    )
    parser.add_argument(
        "packages",
        nargs="*",
        help="Restrict to these package names (default: all).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any package has a pending update; don't write.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a unified diff of proposed changes; don't write.",
    )
    parser.add_argument(
        "--workers",
        type=_positive_int,
        default=8,
        help="Max parallel upstream fetches (default: 8).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if not os.environ.get("GITHUB_TOKEN"):
        print(
            "warning: GITHUB_TOKEN not set; GitHub API requests are rate-limited to 60/hr",
            file=sys.stderr,
        )

    deps = config.load()
    if args.packages:
        unknown = [p for p in args.packages if p not in deps]
        if unknown:
            print(f"error: unknown package(s): {unknown}", file=sys.stderr)
            return 2
        selected = {name: deps[name] for name in args.packages}
    else:
        selected = {name: entry for name, entry in deps.items() if "_updater" in entry}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda item: _fetch_one(*item), selected.items()))

    errors = [r for r in results if r.error is not None]
    for r in errors:
        print(f"error: {r.name}: {r.error}", file=sys.stderr)

    updated = dict(deps)
    for r in results:
        if r.release is None:
            continue
        updated[r.name] = _apply(deps[r.name], r.release)

    before = config.serialize(deps)
    after = config.serialize(updated)

    if args.check:
        if before != after:
            print("dependencies.json is out of date:", file=sys.stderr)
            print(_render_diff(before, after), file=sys.stderr)
            return 1
        return 1 if errors else 0

    if args.dry_run:
        if before == after:
            print("no updates")
        else:
            sys.stdout.write(_render_diff(before, after))
        return 1 if errors else 0

    if before != after:
        config.dump(updated)
        sys.stdout.write(_render_diff(before, after))
    else:
        print("no updates")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
