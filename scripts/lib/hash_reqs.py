#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import argparse
import hashlib

if False:
    from typing import Iterable, List, MutableSet

def expand_reqs_helper(fpath, visited):
    # type: (str, MutableSet[str]) -> List[str]
    if fpath in visited:
        return []
    else:
        visited.add(fpath)

    curr_dir = os.path.dirname(fpath)
    result = [] # type: List[str]

    for line in open(fpath):
        if line.startswith('#'):
            continue
        dep = line.split(" #", 1)[0].strip() # remove comments and strip whitespace
        if dep:
            if dep.startswith('-r'):
                child = os.path.join(curr_dir, dep[3:])
                result += expand_reqs_helper(child, visited)
            else:
                result.append(dep)
    return result

def expand_reqs(fpath):
    # type: (str) -> List[str]
    """
    Returns a sorted list of unique dependencies specified by the requirements file `fpath`.
    Removes comments from the output and recursively visits files specified inside `fpath`.
    `fpath` can be either an absolute path or a relative path.
    """
    absfpath = os.path.abspath(fpath)
    output = expand_reqs_helper(absfpath, set())
    return sorted(set(output))

def hash_deps(deps):
    # type: (Iterable[str]) -> str
    deps_str = "\n".join(deps) + "\n"
    return hashlib.sha1(deps_str.encode('utf-8')).hexdigest()

def main():
    # type: () -> int
    description = ("Finds the SHA1 hash of list of dependencies in a requirements file"
                   " after recursively visiting all files specified in it.")
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("fpath", metavar="FILE",
                        help="Path to requirements file")
    parser.add_argument("--print", dest="print_reqs", action='store_true',
                        help="Print all dependencies")
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
