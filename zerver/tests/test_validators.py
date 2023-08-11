import re
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError

from zerver.lib.exceptions import InvalidJSONError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.types import Validator
from zerver.lib.validator import (
    check_bool,
    check_capped_string,
    check_color,
    check_dict,
    check_dict_only,
    check_float,
    check_int,
    check_int_in,
    check_list,
    check_none_or,
    check_short_string,
    check_string,
    check_string_fixed_length,
    check_string_in,
    check_string_or_int,
    check_string_or_int_list,
    check_union,
    check_url,
    equals,
    to_non_negative_int,
    to_wild_value,
)

if settings.ZILENCER_ENABLED:
    pass

if TYPE_CHECKING:
    pass


class ValidatorTestCase(ZulipTestCase):
    def test_check_string(self) -> None:
        x: Any = "hello"
        check_string("x", x)

        x = 4
        with self.assertRaisesRegex(ValidationError, r"x is not a string"):
            check_string("x", x)

    def test_check_string_fixed_length(self) -> None:
        x: Any = "hello"
        check_string_fixed_length(5)("x", x)

        x = 4
        with self.assertRaisesRegex(ValidationError, r"x is not a string"):
            check_string_fixed_length(5)("x", x)

        x = "helloz"
        with self.assertRaisesRegex(ValidationError, r"x has incorrect length 6; should be 5"):
            check_string_fixed_length(5)("x", x)

        x = "hi"
        with self.assertRaisesRegex(ValidationError, r"x has incorrect length 2; should be 5"):
            check_string_fixed_length(5)("x", x)

    def test_check_capped_string(self) -> None:
        x: Any = "hello"
        check_capped_string(5)("x", x)

        x = 4
        with self.assertRaisesRegex(ValidationError, r"x is not a string"):
            check_capped_string(5)("x", x)

        x = "helloz"
        with self.assertRaisesRegex(ValidationError, r"x is too long \(limit: 5 characters\)"):
            check_capped_string(5)("x", x)

        x = "hi"
        check_capped_string(5)("x", x)

    def test_check_string_in(self) -> None:
        check_string_in(["valid", "othervalid"])("Test", "valid")
        with self.assertRaisesRegex(ValidationError, r"Test is not a string"):
            check_string_in(["valid", "othervalid"])("Test", 15)
        check_string_in(["valid", "othervalid"])("Test", "othervalid")
        with self.assertRaisesRegex(ValidationError, r"Invalid Test"):
            check_string_in(["valid", "othervalid"])("Test", "invalid")

    def test_check_int_in(self) -> None:
        check_int_in([1])("Test", 1)
        with self.assertRaisesRegex(ValidationError, r"Invalid Test"):
            check_int_in([1])("Test", 2)
        with self.assertRaisesRegex(ValidationError, r"Test is not an integer"):
            check_int_in([1])("Test", "t")

    def test_check_short_string(self) -> None:
        x: Any = "hello"
        check_short_string("x", x)

        x = "x" * 201
        with self.assertRaisesRegex(ValidationError, r"x is too long \(limit: 50 characters\)"):
            check_short_string("x", x)

        x = 4
        with self.assertRaisesRegex(ValidationError, r"x is not a string"):
            check_short_string("x", x)

    def test_check_bool(self) -> None:
        x: Any = True
        check_bool("x", x)

        x = 4
        with self.assertRaisesRegex(ValidationError, r"x is not a boolean"):
            check_bool("x", x)

    def test_check_int(self) -> None:
        x: Any = 5
        check_int("x", x)

        x = [{}]
        with self.assertRaisesRegex(ValidationError, r"x is not an integer"):
            check_int("x", x)

    def test_to_non_negative_int(self) -> None:
        self.assertEqual(to_non_negative_int("x", "5"), 5)
        with self.assertRaisesRegex(ValueError, "argument is negative"):
            to_non_negative_int("x", "-1")
        with self.assertRaisesRegex(ValueError, re.escape("5 is too large (max 4)")):
            to_non_negative_int("x", "5", max_int_size=4)
        with self.assertRaisesRegex(ValueError, re.escape(f"{2**32} is too large (max {2**32-1})")):
            to_non_negative_int("x", str(2**32))

    def test_check_float(self) -> None:
        x: Any = 5.5
        check_float("x", x)

        x = 5
        with self.assertRaisesRegex(ValidationError, r"x is not a float"):
            check_float("x", x)

        x = [{}]
        with self.assertRaisesRegex(ValidationError, r"x is not a float"):
            check_float("x", x)

    def test_check_color(self) -> None:
        x = ["#000099", "#80ffaa", "#80FFAA", "#abcd12", "#ffff00", "#ff0", "#f00"]  # valid
        y = ["000099", "#80f_aa", "#80fraa", "#abcd1234", "blue"]  # invalid
        z = 5  # invalid

        for hex_color in x:
            check_color("color", hex_color)

        for hex_color in y:
            with self.assertRaisesRegex(ValidationError, r"color is not a valid hex color code"):
                check_color("color", hex_color)

        with self.assertRaisesRegex(ValidationError, r"color is not a string"):
            check_color("color", z)

    def test_check_list(self) -> None:
        x: Any = 999
        with self.assertRaisesRegex(ValidationError, r"x is not a list"):
            check_list(check_string)("x", x)

        x = ["hello", 5]
        with self.assertRaisesRegex(ValidationError, r"x\[1\] is not a string"):
            check_list(check_string)("x", x)

        x = [["yo"], ["hello", "goodbye", 5]]
        with self.assertRaisesRegex(ValidationError, r"x\[1\]\[2\] is not a string"):
            check_list(check_list(check_string))("x", x)

        x = ["hello", "goodbye", "hello again"]
        with self.assertRaisesRegex(ValidationError, r"x should have exactly 2 items"):
            check_list(check_string, length=2)("x", x)

    def test_check_dict(self) -> None:
        keys: List[Tuple[str, Validator[object]]] = [
            ("names", check_list(check_string)),
            ("city", check_string),
        ]

        x: Any = {
            "names": ["alice", "bob"],
            "city": "Boston",
        }
        check_dict(keys)("x", x)

        x = 999
        with self.assertRaisesRegex(ValidationError, r"x is not a dict"):
            check_dict(keys)("x", x)

        x = {}
        with self.assertRaisesRegex(ValidationError, r"names key is missing from x"):
            check_dict(keys)("x", x)

        x = {
            "names": ["alice", "bob", {}],
        }
        with self.assertRaisesRegex(ValidationError, r'x\["names"\]\[2\] is not a string'):
            check_dict(keys)("x", x)

        x = {
            "names": ["alice", "bob"],
            "city": 5,
        }
        with self.assertRaisesRegex(ValidationError, r'x\["city"\] is not a string'):
            check_dict(keys)("x", x)

        x = {
            "names": ["alice", "bob"],
            "city": "Boston",
        }
        with self.assertRaisesRegex(ValidationError, r"x contains a value that is not a string"):
            check_dict(value_validator=check_string)("x", x)

        x = {
            "city": "Boston",
        }
        check_dict(value_validator=check_string)("x", x)

        # test dict_only
        x = {
            "names": ["alice", "bob"],
            "city": "Boston",
        }
        check_dict_only(keys)("x", x)

        x = {
            "names": ["alice", "bob"],
            "city": "Boston",
            "state": "Massachusetts",
        }
        with self.assertRaisesRegex(ValidationError, r"Unexpected arguments: state"):
            check_dict_only(keys)("x", x)

        # Test optional keys
        optional_keys = [
            ("food", check_list(check_string)),
            ("year", check_int),
        ]

        x = {
            "names": ["alice", "bob"],
            "city": "Boston",
            "food": ["Lobster spaghetti"],
        }

        check_dict(keys)("x", x)  # since _allow_only_listed_keys is False

        with self.assertRaisesRegex(ValidationError, r"Unexpected arguments: food"):
            check_dict_only(keys)("x", x)

        check_dict_only(keys, optional_keys)("x", x)

        x = {
            "names": ["alice", "bob"],
            "city": "Boston",
            "food": "Lobster spaghetti",
        }
        with self.assertRaisesRegex(ValidationError, r'x\["food"\] is not a list'):
            check_dict_only(keys, optional_keys)("x", x)

    def test_encapsulation(self) -> None:
        # There might be situations where we want deep
        # validation, but the error message should be customized.
        # This is an example.
        def check_person(val: object) -> Dict[str, object]:
            try:
                return check_dict(
                    [
                        ("name", check_string),
                        ("age", check_int),
                    ]
                )("_", val)
            except ValidationError:
                raise ValidationError("This is not a valid person")

        person = {"name": "King Lear", "age": 42}
        check_person(person)

        nonperson = "misconfigured data"
        with self.assertRaisesRegex(ValidationError, r"This is not a valid person"):
            check_person(nonperson)

    def test_check_union(self) -> None:
        x: Any = 5
        check_union([check_string, check_int])("x", x)

        x = "x"
        check_union([check_string, check_int])("x", x)

        x = [{}]
        with self.assertRaisesRegex(ValidationError, r"x is not an allowed_type"):
            check_union([check_string, check_int])("x", x)

    def test_equals(self) -> None:
        x: Any = 5
        equals(5)("x", x)
        with self.assertRaisesRegex(ValidationError, r"x != 6 \(5 is wrong\)"):
            equals(6)("x", x)

    def test_check_none_or(self) -> None:
        x: Any = 5
        check_none_or(check_int)("x", x)
        x = None
        check_none_or(check_int)("x", x)
        x = "x"
        with self.assertRaisesRegex(ValidationError, r"x is not an integer"):
            check_none_or(check_int)("x", x)

    def test_check_url(self) -> None:
        url: Any = "http://127.0.0.1:5002/"
        check_url("url", url)

        url = "http://zulip-bots.example.com/"
        check_url("url", url)

        url = "http://127.0.0"
        with self.assertRaisesRegex(ValidationError, r"url is not a URL"):
            check_url("url", url)

        url = 99.3
        with self.assertRaisesRegex(ValidationError, r"url is not a string"):
            check_url("url", url)

    def test_check_string_or_int_list(self) -> None:
        x: Any = "string"
        check_string_or_int_list("x", x)

        x = [1, 2, 4]
        check_string_or_int_list("x", x)

        x = None
        with self.assertRaisesRegex(ValidationError, r"x is not a string or an integer list"):
            check_string_or_int_list("x", x)

        x = [1, 2, "3"]
        with self.assertRaisesRegex(ValidationError, r"x\[2\] is not an integer"):
            check_string_or_int_list("x", x)

    def test_check_string_or_int(self) -> None:
        x: Any = "string"
        check_string_or_int("x", x)

        x = 1
        check_string_or_int("x", x)

        x = None
        with self.assertRaisesRegex(ValidationError, r"x is not a string or integer"):
            check_string_or_int("x", x)

    def test_wild_value(self) -> None:
        x = to_wild_value("x", '{"a": 1, "b": ["c", false, null]}')

        self.assertEqual(x, x)
        self.assertTrue(x)
        self.assertEqual(len(x), 2)
        self.assertEqual(list(x.keys()), ["a", "b"])
        self.assertEqual(list(x.values()), [1, ["c", False, None]])
        self.assertEqual(list(x.items()), [("a", 1), ("b", ["c", False, None])])
        self.assertTrue("a" in x)
        self.assertEqual(x["a"], 1)
        self.assertEqual(x.get("a"), 1)
        self.assertEqual(x.get("z"), None)
        self.assertEqual(x.get("z", x["a"]).tame(check_int), 1)
        self.assertEqual(x["a"].tame(check_int), 1)
        self.assertEqual(x["b"], x["b"])
        self.assertTrue(x["b"])
        self.assertEqual(len(x["b"]), 3)
        self.assert_length(list(x["b"]), 3)
        self.assertEqual(x["b"][0].tame(check_string), "c")
        self.assertFalse(x["b"][1])
        self.assertFalse(x["b"][2])

        with self.assertRaisesRegex(ValidationError, r"x is not a string"):
            x.tame(check_string)
        with self.assertRaisesRegex(ValidationError, r"x is not a list"):
            x[0]
        with self.assertRaisesRegex(ValidationError, r"x\['z'\] is missing"):
            x["z"]
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a list"):
            x["a"][0]
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a list"):
            iter(x["a"])
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a dict"):
            x["a"]["a"]
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a dict"):
            x["a"].get("a")
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a dict"):
            _ = "a" in x["a"]
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a dict"):
            x["a"].keys()
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a dict"):
            x["a"].values()
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] is not a dict"):
            x["a"].items()
        with self.assertRaisesRegex(ValidationError, r"x\['a'\] does not have a length"):
            len(x["a"])
        with self.assertRaisesRegex(ValidationError, r"x\['b'\]\[1\] is not a string"):
            x["b"][1].tame(check_string)
        with self.assertRaisesRegex(ValidationError, r"x\['b'\]\[99\] is missing"):
            x["b"][99]
        with self.assertRaisesRegex(ValidationError, r"x\['b'\] is not a dict"):
            x["b"]["b"]

        with self.assertRaisesRegex(InvalidJSONError, r"Malformed JSON"):
            to_wild_value("x", "invalidjson")
