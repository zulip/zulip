from typing import TypeVar

T = TypeVar("T")


def mark_sanitized(arg: T) -> T:
    return arg
