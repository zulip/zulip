#!/usr/bin/env python3
"""
Zulip Documentation - Markdown Quality Validator
Lightweight zero-dependency validation utility for open-source documentation.
Validates code fence parity, link syntax, heading structures, and file integrity.
"""

import os
import sys
import re
import argparse


def inspect_markdown_file(filepath):
    """
    Inspects a single markdown file for syntax issues and formatting errors.
    Returns a dict with status ('VALID' or 'INVALID'), errors list, and warnings list.
    """
    errors = []
    warnings = []

    if not os.path.exists(filepath):
        return {
            "status": "INVALID",
            "file": filepath,
            "errors": [f"File not found: {filepath}"],
            "warnings": [],
            "stats": {"lines": 0, "code_blocks": 0, "headings": 0}
        }

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return {
            "status": "INVALID",
            "file": filepath,
            "errors": [f"Failed to read file: {str(e)}"],
            "warnings": [],
            "stats": {"lines": 0, "code_blocks": 0, "headings": 0}
        }

    if not lines or len("".join(lines).strip()) == 0:
        return {
            "status": "INVALID",
            "file": filepath,
            "errors": ["File is empty or contains only whitespace."],
            "warnings": [],
            "stats": {"lines": 0, "code_blocks": 0, "headings": 0}
        }

    in_code_block = False
    code_block_start_line = 0
    code_blocks_count = 0
    headings_count = 0
    last_heading_line = None
    last_heading_text = None
    content_after_last_heading = False

    code_fence_pattern = re.compile(r"^(\s*)```")
    empty_link_pattern = re.compile(r"\[([^\]]+)\]\(\s*\)")
    heading_pattern = re.compile(r"^(#{1,6})\s*(.*)")
    empty_heading_pattern = re.compile(r"^(#{1,6})\s*$")

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()

        fence_match = code_fence_pattern.match(line)
        if fence_match:
            if not in_code_block:
                in_code_block = True
                code_block_start_line = idx
                code_blocks_count += 1
            else:
                in_code_block = False
            continue

        if in_code_block:
            continue

        if empty_heading_pattern.match(line):
            errors.append(f"Line {idx}: Heading without title text.")
            continue

        heading_match = heading_pattern.match(line)
        if heading_match:
            headings_count += 1
            if last_heading_line is not None and not content_after_last_heading:
                warnings.append(
                    f"Line {last_heading_line}: Heading '{last_heading_text}' has no body content before next heading."
                )
            last_heading_line = idx
            last_heading_text = heading_match.group(2).strip()
            content_after_last_heading = False
            continue

        if line.strip():
            content_after_last_heading = True

        if empty_link_pattern.search(line):
            errors.append(f"Line {idx}: Empty Markdown link target detected (empty parenthesis).")

    if in_code_block:
        errors.append(
            f"Line {code_block_start_line}: Unclosed Markdown code fence (```) extends to end of file."
        )

    status = "INVALID" if len(errors) > 0 else "VALID"
    return {
        "status": status,
        "file": filepath,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "lines": len(lines),
            "code_blocks": code_blocks_count,
            "headings": headings_count
        }
    }


def validate_paths(paths, verbose=False):
    all_files = []
    for p in paths:
        if os.path.isfile(p):
            if p.lower().endswith(".md"):
                all_files.append(p)
        elif os.path.isdir(p):
            for root, _, filenames in os.walk(p):
                for f in filenames:
                    if f.lower().endswith(".md"):
                        all_files.append(os.path.join(root, f))
        else:
            all_files.append(p)

    results = []
    for f in all_files:
        res = inspect_markdown_file(f)
        results.append(res)
    return results


def print_report(results, verbose=False):
    total_files = len(results)
    passed_count = sum(1 for r in results if r["status"] == "VALID")
    failed_count = total_files - passed_count
    total_errors = sum(len(r["errors"]) for r in results)
    total_warnings = sum(len(r["warnings"]) for r in results)

    print("\n" + "=" * 70)
    print("  ZULIP OPEN-SOURCE - MARKDOWN QUALITY VALIDATOR")
    print("=" * 70)

    for r in results:
        badge = "[VALID]" if r["status"] == "VALID" else "[INVALID]"
        print(f"\n{badge:<10} {r['file']}")
        print(f"           Lines: {r['stats']['lines']} | Headings: {r['stats']['headings']} | Code Blocks: {r['stats']['code_blocks']}")

        if r["errors"]:
            for err in r["errors"]:
                print(f"           [ERROR]   {err}")
        if r["warnings"] and (verbose or r["status"] == "INVALID"):
            for warn in r["warnings"]:
                print(f"           [WARNING] {warn}")

    print("\n" + "-" * 70)
    print(f"SUMMARY: {passed_count}/{total_files} files PASSED ({failed_count} failed)")
    print(f"Total Errors: {total_errors} | Total Warnings: {total_warnings}")
    print("=" * 70 + "\n")

    return 0 if failed_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Lightweight Markdown Quality Validator for Zulip Open Source"
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["sample_doc.md"],
        help="Path to Markdown file(s) or directories to validate"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Display detailed warnings in report"
    )
    args = parser.parse_args()

    results = validate_paths(args.targets, verbose=args.verbose)
    exit_code = print_report(results, verbose=args.verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
