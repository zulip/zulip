# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html
import os
import subprocess
from typing import Optional


def try_git_describe() -> Optional[str]:
    try:  # nocoverage
        return subprocess.check_output(
            ["git", "describe", "--tags", "--match=[0-9]*", "--always", "--dirty", "--long"],
            stderr=subprocess.PIPE,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):  # nocoverage
        return None
