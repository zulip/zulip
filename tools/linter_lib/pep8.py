from typing import List

from zulint.linters import run_command
from zulint.printer import colors


def check_pep8(files: List[str]) -> bool:
    if not files:
        return False
    return run_command("pep8", next(colors), ["pycodestyle", "--", *files]) != 0
