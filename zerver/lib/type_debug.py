from __future__ import print_function

import sys
import functools

from typing import Any, Callable, IO, Mapping, Sequence, TypeVar
from six import text_type

def get_mapping_type_str(x):
    # type: (Mapping) -> str
    container_type = type(x).__name__
    if not x:
        if container_type == 'dict':
            return '{}'
        else:
            return container_type + '([])'
    key = next(iter(x))
    key_type = get_type_str(key)
    value_type = get_type_str(x[key])
    if container_type == 'dict':
        if len(x) == 1:
            return '{%s: %s}' % (key_type, value_type)
        else:
            return '{%s: %s, ...}' % (key_type, value_type)
    else:
        if len(x) == 1:
            return '%s([(%s, %s)])' % (container_type, key_type, value_type)
        else:
            return '%s([(%s, %s), ...])' % (container_type, key_type, value_type)

def get_sequence_type_str(x):
    # type: (Sequence) -> str
    container_type = type(x).__name__
    if not x:
        if container_type == 'list':
            return '[]'
        else:
            return container_type + '([])'
    elem_type = get_type_str(x[0])
    if container_type == 'list':
        if len(x) == 1:
            return '[' + elem_type + ']'
        else:
            return '[' + elem_type + ', ...]'
    else:
        if len(x) == 1:
            return '%s([%s])' % (container_type, elem_type)
        else:
            return '%s([%s, ...])' % (container_type, elem_type)

expansion_blacklist = [text_type, bytes]

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
    elif isinstance(x, Mapping):
        return get_mapping_type_str(x)
    elif isinstance(x, Sequence) and not any(isinstance(x, t) for t in expansion_blacklist):
        return get_sequence_type_str(x)
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
