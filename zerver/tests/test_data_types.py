from zerver.lib.data_types import (
    DictType,
    EnumType,
    Equals,
    ListType,
    NumberType,
    OptionalType,
    StringDictType,
    TupleType,
    UnionType,
    UrlType,
    schema,
)
from zerver.lib.test_classes import ZulipTestCase


class MiscTest(ZulipTestCase):
    def test_data_type_schema(self) -> None:
        """
        We really only test this to get test coverage.  The
        code covered here is really only used in testing tools.
        """
        test_schema = DictType(
            [
                ("type", Equals("realm")),
                ("maybe_n", OptionalType(int)),
                ("s", str),
                ("timestamp", NumberType()),
                ("flag", bool),
                ("tup", TupleType([int, str])),
                ("level", EnumType([1, 2, 3])),
                ("lst", ListType(int)),
                ("config", StringDictType(str)),
                ("value", UnionType([int, str])),
                ("url", UrlType()),
            ]
        )
        expected = """
test (dict):
    config (string_dict):
        value: str
    flag: bool
    level in [1, 2, 3]
    lst (list):
        type: int
    maybe_n: int
    s: str
    timestamp: number
    tup (tuple):
        0: int
        1: str
    type in ['realm']
    url: str
    value (union):
        type: int
        type: str
"""
        self.assertEqual(schema("test", test_schema).strip(), expected.strip())
