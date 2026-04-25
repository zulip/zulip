import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_DATA = ROOT / "var" / ".coverage"
COVERAGE_RC = ROOT / "tools" / "coveragerc"

CODE_TARGETS = [
    "zerver/views/tasks.py",
]


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def _pick_file_summary(payload: dict[str, object], suffix: str) -> dict[str, object] | None:
    files = payload.get("files")
    if not isinstance(files, dict):
        return None
    for path_key, meta in files.items():
        if _norm(str(path_key)).endswith(suffix) and isinstance(meta, dict):
            summary = meta.get("summary")
            if isinstance(summary, dict):
                return summary
    return None


def _branch_coverage_percent(summary: dict[str, object]) -> float | None:
    if "percent_branches_covered" in summary:
        v = summary["percent_branches_covered"]
        if isinstance(v, int | float):
            return round(float(v), 2)
    num_branches = summary.get("num_branches")
    covered = summary.get("covered_branches")
    if isinstance(num_branches, int) and num_branches > 0 and isinstance(covered, int):
        return round(100.0 * covered / num_branches, 2)
    return None


def _build_code_coverage_entry(summary: dict[str, object]) -> dict[str, object]:
    line_pct = summary.get("percent_covered")
    if isinstance(line_pct, int | float):
        line_pct = round(float(line_pct), 2)
    else:
        line_pct = None
    return {
        "line_coverage_percent": line_pct,
        "branch_coverage_percent": _branch_coverage_percent(summary),
        "statements": summary.get("num_statements"),
        "covered_statements": summary.get("covered_lines"),
        "missing_statements": summary.get("missing_lines"),
        "num_branches": summary.get("num_branches"),
        "covered_branches": summary.get("covered_branches"),
        "missing_branches": summary.get("missing_branches"),
    }


def _print_metrics(metrics: dict[str, object]) -> None:
    print("Task backend coverage (from task-related unit tests + coverage.py)")
    print()
    v = metrics.get("coverage_version")
    if v is not None:
        print(f"  coverage.py version: {v}")
    primary = metrics.get("zerver_views_tasks_line_coverage_percent")
    if primary is not None:
        print(f"  zerver/views/tasks.py line coverage: {primary}%")
    by_file = metrics.get("code_coverage_by_file")
    if isinstance(by_file, dict):
        for path, entry in by_file.items():
            print()
            print(f"  {path}")
            if not isinstance(entry, dict):
                print(f"    (unexpected: {entry!r})")
                continue
            if "error" in entry:
                print(f"    error: {entry['error']}")
                continue
            lp = entry.get("line_coverage_percent")
            bp = entry.get("branch_coverage_percent")
            print(f"    line coverage:    {lp}%")
            if bp is not None:
                print(f"    branch coverage:  {bp}%")
            st = entry.get("statements")
            cov = entry.get("covered_statements")
            miss = entry.get("missing_statements")
            print(f"    statements:       {st} ({cov} covered, {miss} missing)")
            nb = entry.get("num_branches")
            if isinstance(nb, int) and nb > 0:
                cb = entry.get("covered_branches")
                mb = entry.get("missing_branches")
                print(f"    branches:         {nb} ({cb} covered, {mb} missing)")
    totals = metrics.get("coverage_run_totals")
    if isinstance(totals, dict):
        print()
        print("  Full-run totals (all code measured in this coverage session):")
        for key in ("percent_covered", "covered_lines", "num_statements", "missing_lines"):
            if key in totals:
                print(f"    {key}: {totals[key]}")


def main() -> int:
    suites = [
        "zerver.tests.test_tasks",
        "zerver.tests.test_tasks_api",
        "zerver.tests.test_tasks_integration",
    ]
    env = {**os.environ, "COVERAGE_FILE": str(COVERAGE_DATA)}
    proc = subprocess.run(
        [
            str(ROOT / "tools" / "test-backend"),
            *suites,
            "--coverage",
            "--no-html-report",
            "--no-cov-cleanup",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        return proc.returncode

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td) / "coverage.json"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "json",
                f"--data-file={COVERAGE_DATA}",
                f"--rcfile={COVERAGE_RC}",
                "-o",
                str(tmp_path),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        with tmp_path.open() as f:
            payload = json.load(f)

    code_coverage: dict[str, dict[str, object]] = {}
    for suffix in CODE_TARGETS:
        summary = _pick_file_summary(payload, suffix)
        if summary is None:
            code_coverage[suffix] = {"error": "file not present in coverage data"}
        else:
            code_coverage[suffix] = _build_code_coverage_entry(summary)

    meta = payload.get("meta")
    totals = payload.get("totals")
    tasks_summary = _pick_file_summary(payload, CODE_TARGETS[0])
    primary_line_pct = None
    if tasks_summary is not None:
        pc = tasks_summary.get("percent_covered")
        if isinstance(pc, int | float):
            primary_line_pct = round(float(pc), 2)

    metrics: dict[str, object] = {
        "kind": "python_line_and_branch_coverage",
        "scope": "task HTTP handlers (zerver.views.tasks) exercised by task-related backend tests",
        "zerver_views_tasks_line_coverage_percent": primary_line_pct,
        "code_coverage_by_file": code_coverage,
        "coverage_run_totals": totals if isinstance(totals, dict) else None,
        "coverage_version": meta.get("version") if isinstance(meta, dict) else None,
    }
    _print_metrics(metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
