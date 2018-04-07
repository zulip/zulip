
import sys
from unittest import TestCase
from io import StringIO

from zerver.lib.type_debug import print_types

from typing import Any, Callable, Dict, Iterable, Tuple, TypeVar, List

T = TypeVar('T')

def add(x: Any=0, y: Any=0) -> Any:
    return x + y

def to_dict(v: Iterable[Tuple[Any, Any]]=[]) -> Dict[Any, Any]:
    return dict(v)

class TypesPrintTest(TestCase):

    # These 2 methods are needed to run tests with our custom test-runner
    def _pre_setup(self) -> None:
        pass

    def _post_teardown(self) -> None:
        pass

    def check_signature(self, signature: str, retval: T, func: Callable[..., T],
                        *args: Any, **kwargs: Any) -> None:
        """
        Checks if print_types outputs `signature` when func is called with *args and **kwargs.
        Do not decorate func with print_types before passing into this function.
        func will be decorated with print_types within this function.
        """
        try:
            original_stdout = sys.stdout
            sys.stdout = StringIO()
            self.assertEqual(retval, print_types(func)(*args, **kwargs))
            self.assertEqual(sys.stdout.getvalue().strip(), signature)
        finally:
            sys.stdout = original_stdout

    def test_empty(self) -> None:
        def empty_func() -> None:
            pass
        self.check_signature("empty_func() -> None", None, empty_func)
        self.check_signature("<lambda>() -> None", None, (lambda: None))

    def test_basic(self) -> None:
        self.check_signature("add(float, int) -> float",
                             5.0, add, 2.0, 3)
        self.check_signature("add(float, y=int) -> float",
                             5.0, add, 2.0, y=3)
        self.check_signature("add(x=int) -> int", 2, add, x=2)
        self.check_signature("add() -> int", 0, add)

    def test_list(self) -> None:
        self.check_signature("add([], [str]) -> [str]",
                             ['two'], add, [], ['two'])
        self.check_signature("add([int], [str]) -> [int, ...]",
                             [2, 'two'], add, [2], ['two'])
        self.check_signature("add([int, ...], y=[]) -> [int, ...]",
                             [2, 'two'], add, [2, 'two'], y=[])

    def test_dict(self) -> None:
        self.check_signature("to_dict() -> {}", {}, to_dict)
        self.check_signature("to_dict([(int, str)]) -> {int: str}",
                             {2: 'two'}, to_dict, [(2, 'two')])
        self.check_signature("to_dict(((int, str),)) -> {int: str}",
                             {2: 'two'}, to_dict, ((2, 'two'),))
        self.check_signature("to_dict([(int, str), ...]) -> {int: str, ...}",
                             {1: 'one', 2: 'two'}, to_dict, [(1, 'one'), (2, 'two')])

    def test_tuple(self) -> None:
        self.check_signature("add((), ()) -> ()",
                             (), add, (), ())
        self.check_signature("add((int,), (str,)) -> (int, str)",
                             (1, 'one'), add, (1,), ('one',))
        self.check_signature("add(((),), ((),)) -> ((), ())",
                             ((), ()), add, ((),), ((),))

    def test_class(self) -> None:
        class A:
            pass

        class B(str):
            pass

        self.check_signature("<lambda>(A) -> str", 'A', (lambda x: x.__class__.__name__), A())
        self.check_signature("<lambda>(B) -> int", 5, (lambda x: len(x)), B("hello"))

    def test_sequence(self) -> None:
        class A(List[Any]):
            pass

        class B(List[Any]):
            pass

        self.check_signature("add(A([]), B([str])) -> [str]",
                             ['two'], add, A([]), B(['two']))
        self.check_signature("add(A([int]), B([str])) -> [int, ...]",
                             [2, 'two'], add, A([2]), B(['two']))
        self.check_signature("add(A([int, ...]), y=B([])) -> [int, ...]",
                             [2, 'two'], add, A([2, 'two']), y=B([]))

    def test_mapping(self) -> None:
        class A(Dict[Any, Any]):
            pass

        def to_A(v: Iterable[Tuple[Any, Any]]=[]) -> A:
            return A(v)

        self.check_signature("to_A() -> A([])", A(()), to_A)
        self.check_signature("to_A([(int, str)]) -> A([(int, str)])",
                             {2: 'two'}, to_A, [(2, 'two')])
        self.check_signature("to_A([(int, str), ...]) -> A([(int, str), ...])",
                             {1: 'one', 2: 'two'}, to_A, [(1, 'one'), (2, 'two')])
        self.check_signature("to_A(((int, str), (int, str))) -> A([(int, str), ...])",
                             {1: 'one', 2: 'two'}, to_A, ((1, 'one'), (2, 'two')))
