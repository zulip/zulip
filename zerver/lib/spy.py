import os

from typing import (
    get_type_hints,
    _Any,
    Any,
    Dict,
    List,
    Iterable,
    Sequence,
    Mapping,
    Union,
)

if os.path.exists("spy.txt"):
    raise Exception("remove or rename spy.txt first")

def write(*args):
    print(*args)
    with open("spy.txt", "a") as f:
        f.write(" ".join(str(s) for s in args))
        f.write("\n")

def obj_type(x):
    if isinstance(x, list):
        if len(x) == 0:
            return "List[Any]"
        return f"List:\n{obj_type(x[0])}\n"
    if isinstance(x, dict):
        s = "class SomeDict(TypedDict):\n"
        for k, v in sorted(x.items()):
            s += f"    {k}: {obj_type(v)}\n"
        return s
    if type(x) in [int, str, float]:
        return type(x).__name__
    raise ValueError('unsupported type')

def get_mypy_sig(mypy_type: Any) -> str:
    '''
    This is simplified, canonical representation of
    a mypy type.  It has only been tested on python3.6.

    We could use https://github.com/ilevkivskyi/typing_inspect
    to improve this.
    '''

    if isinstance(mypy_type, _Any):
        return "Any"

    if hasattr(mypy_type, '__origin__'):
        if mypy_type.__origin__ == Union:
            args = mypy_type.__args__
            innards = ', '.join(sorted(
                get_mypy_sig(arg) for arg in args
            ))
            return f'Union[{innards}]'

        if mypy_type.__origin__ in {Iterable, List, Sequence}:
            arg = mypy_type.__args__[0]
            return f'List[{get_mypy_sig(arg)}]'

        if mypy_type.__origin__ in {Dict, Mapping}:
            args = mypy_type.__args__
            k = get_mypy_sig(args[0])
            v = get_mypy_sig(args[1])

            # we lie about the value here, since legacy
            # code often promises a more strict type
            # then we are actually enforcing
            return f'Dict[{k}, {v}]'

    if not hasattr(mypy_type, '__name__'):
        return "object"

    return mypy_type.__name__

def spy(f):
    try:
        type_hints = get_type_hints(f)
    except:
        print(f"{f.__name__} fails for get_type_hints")
        return f

    mypy = {
        k: get_mypy_sig(v)
        for k, v in type_hints.items()
    }

    def arg_name(i):
        return f.__code__.co_varnames[i]

    def wrapped(*args, **kwargs):
        for i, arg in enumerate(args):
            name = arg_name(i)
            if name == "self":
                continue

            mypy_sig = mypy[name]
            if 'Any' not in mypy_sig:
                continue

            if arg == [] and mypy_sig.startswith("List"):
                # type info for empty lists is
                # basically useless
                continue

            try:
                obj_sig = obj_type(arg)
            except ValueError:
                continue

            write('\nFUNC:', f.__module__, f.__name__, name)
            write(mypy_sig)
            write("\nactual data:\n")
            write(obj_sig)
        ret = f(*args, **kwargs)
        # We should eventually handle return values.
        # print(ret)
        return ret

    return wrapped
