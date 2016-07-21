from __future__ import print_function

import sys
import functools

from typing import Any, Callable, IO, TypeVar

def get_type_str(x):
    # type: (Any) -> str
    if x is None:
        return 'None'
    elif isinstance(x, tuple):
        types = []
        for v in x:
            types.append(get_type_str(v))
        if len(x) == 1:
            return '(' + types[0] + ',)'
        else:
            return '(' + ', '.join(types) + ')'
    else:
        return type(x).__name__

FuncT = TypeVar('FuncT', bound=Callable)

def print_types_to(file_obj):
    # type: (IO[str]) -> Callable[[FuncT], FuncT]
    def decorator(func):
        # type: (FuncT) -> FuncT
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # type: (*Any, **Any) -> Any
            arg_types = [get_type_str(arg) for arg in args]
            kwarg_types = [key + "=" + get_type_str(value) for key, value in kwargs.items()]
            ret_val = func(*args, **kwargs)
            output = "%s(%s) -> %s" % (func.__name__,
                                    ", ".join(arg_types + kwarg_types),
                                    get_type_str(ret_val))
            print(output, file=file_obj)
            return ret_val
        return wrapper # type: ignore # https://github.com/python/mypy/issues/1927
    return decorator

def print_types(func):
    # type: (FuncT) -> FuncT
    return print_types_to(sys.stdout)(func) # type: ignore # https://github.com/python/mypy/issues/1551
