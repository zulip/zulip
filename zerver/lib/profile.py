import cProfile
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from typing_extensions import ParamSpec

ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")


def profiled(func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
    """
    This decorator should obviously be used only in a dev environment.
    It works best when surrounding a function that you expect to be
    called once.  One strategy is to write a backend test and wrap the
    test case with the profiled decorator.

    You can run a single test case like this:

        # edit zerver/tests/test_external.py and place @profiled above the test case below
        ./tools/test-backend zerver.tests.test_external.RateLimitTests.test_ratelimit_decrease

    Then view the results like this:

        ./tools/show-profile-results test_ratelimit_decrease.profile

    """

    @wraps(func)
    def wrapped_func(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
        fn = func.__name__ + ".profile"
        prof = cProfile.Profile()
        retval = prof.runcall(func, *args, **kwargs)
        prof.dump_stats(fn)
        return retval

    return wrapped_func
