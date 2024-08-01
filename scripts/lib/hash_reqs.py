#!/usr/bin/env python3
import argparse
import hashlib
import os
import subprocess
import sys
from collections.abc import Iterable


def expand_reqs_helper(fpath: str) -> list[str]:
    result: list[str] = []

    with open(fpath) as f:
        for line in f:
            if line.strip().startswith(("#", "--hash")):
                continue
            dep = line.split(" \\", 1)[0].strip()
            if dep:
                result.append(dep)
    return result


def expand_reqs(fpath: str) -> list[str]:
    """
    Returns a sorted list of unique dependencies specified by the requirements file `fpath`.
    Removes comments from the output and recursively visits files specified inside `fpath`.
    `fpath` can be either an absolute path or a relative path.
    """
    absfpath = os.path.abspath(fpath)
    output = expand_reqs_helper(absfpath)
    return sorted(set(output))


def python_version() -> str:
    """
    Returns the Python version as string 'Python major.minor.patchlevel'
    """
    return subprocess.check_output(["/usr/bin/python3", "-VV"], text=True)


def hash_deps(deps: Iterable[str]) -> str:
    deps_str = "\n".join(deps) + "\n" + python_version()
    return hashlib.sha1(deps_str.encode()).hexdigest()


def main() -> int:
    description = (
        "Finds the SHA1 hash of list of dependencies in a requirements file"
        " after recursively visiting all files specified in it."
    )
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("fpath", metavar="FILE", help="Path to requirements file")
    parser.add_argument(
        "--print", dest="print_reqs", action="store_true", help="Print all dependencies"
    )
    args = parser.parse_args()

    deps = expand_reqs(args.fpath)
    hash = hash_deps(deps)
    print(hash)
    if args.print_reqs:
        for dep in deps:
            print(dep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
