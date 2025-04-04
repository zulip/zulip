"""
This module partly exists to prevent circular dependencies.

It also isolates some fairly yucky code related to the fact
that we have to support two formats of narrow specifications
from users:

    legacy:
        [["stream", "devel"], ["is", mentioned"]

    modern:
        [
            {"operator": "stream", "operand": "devel", "negated": "false"},
            {"operator": "is", "operand": "mentioned", "negated": "false"},
        ]

    And then on top of that, we want to represent narrow
    specification internally as dataclasses.
"""

import os
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from django.conf import settings


@dataclass
class NarrowTerm:
    operator: str
    operand: str | int | list[int]
    negated: bool


@dataclass
class NeverNegatedNarrowTerm(NarrowTerm):
    negated: bool = field(default=False, init=False)
    operand: str


def narrow_dataclasses_from_tuples(
    tups: Collection[Sequence[str]],
) -> Collection[NeverNegatedNarrowTerm]:
    """
    This method assumes that the callers are in our event-handling codepath, and
    therefore as of summer 2023, they do not yet support the "negated" flag.
    """
    return [NeverNegatedNarrowTerm(operator=tup[0], operand=tup[1]) for tup in tups]


stop_words_list: list[str] | None = None


def read_stop_words() -> list[str]:
    global stop_words_list
    if stop_words_list is None:
        file_path = os.path.join(
            settings.DEPLOY_ROOT, "puppet/zulip/files/postgresql/zulip_english.stop"
        )
        with open(file_path) as f:
            stop_words_list = f.read().splitlines()

    return stop_words_list
