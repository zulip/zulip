# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html
import os
import subprocess
import functools


@functools.lru_cache(maxsize=1)  # Cache result to avoid redundant subprocess calls
def try_git_describe() -> str | None:
    try:  # nocoverage
        return subprocess.check_output(
            ["git", "describe", "--tags", "--match=[0-9]*", "--always", "--dirty", "--long"],
            stderr=subprocess.PIPE,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):  # nocoverage
        return None
# made changes
