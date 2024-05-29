# Workaround for missing functools.partial support in mypy
# (https://github.com/python/mypy/issues/1484).

from typing import TYPE_CHECKING, Callable, TypeVar, overload

if TYPE_CHECKING:
    from typing_extensions import Concatenate, ParamSpec

    P = ParamSpec("P")
    T1 = TypeVar("T1")
    T2 = TypeVar("T2")
    T3 = TypeVar("T3")
    T4 = TypeVar("T4")
    R = TypeVar("R")

    @overload
    def partial(func: Callable[P, R], /) -> Callable[P, R]: ...
    @overload
    def partial(func: Callable[Concatenate[T1, P], R], arg1: T1, /) -> Callable[P, R]: ...
    @overload
    def partial(
        func: Callable[Concatenate[T1, T2, P], R], arg1: T1, arg2: T2, /
    ) -> Callable[P, R]: ...
    @overload
    def partial(
        func: Callable[Concatenate[T1, T2, T3, P], R], arg1: T1, arg2: T2, arg3: T3, /
    ) -> Callable[P, R]: ...
    @overload
    def partial(
        func: Callable[Concatenate[T1, T2, T3, T4, P], R], arg1: T1, arg2: T2, arg3: T3, arg4: T4, /
    ) -> Callable[P, R]: ...

    def partial(func: Callable[..., R], /, *args: object) -> Callable[..., R]: ...

else:
    from functools import partial as partial
