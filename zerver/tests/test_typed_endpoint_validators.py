from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.typed_endpoint_validators import (
    check_int_in,
    check_string_in,
    check_timezone,
    check_url,
    to_non_negative_int_or_none,
    to_timezone_or_empty,
)


class ValidatorTestCase(ZulipTestCase):
    def test_check_int_in(self) -> None:
        check_int_in(3, [1, 2, 3])
        with self.assertRaisesRegex(ValueError, "Not in the list of possible values"):
            check_int_in(3, [1, 2])

    def test_check_string_in(self) -> None:
        check_string_in("foo", ["foo", "bar"])
        with self.assertRaisesRegex(ValueError, "Not in the list of possible values"):
            check_string_in("foo", ["bar"])

    def test_check_url(self) -> None:
        check_url("https://example.com")
        with self.assertRaisesRegex(ValueError, "Not a URL"):
            check_url("https://127.0.0..:5000")

    def test_check_timezone(self) -> None:
        self.assertEqual(check_timezone("America/Denver"), "America/Denver")
        # Directory names and overlong names make zoneinfo raise OSError.
        for invalid_timezone in ["invalid/Timezone", "America", "a" * 256]:
            with self.assertRaisesRegex(ValueError, "Not a recognized time zone"):
                check_timezone(invalid_timezone)

    def test_to_timezone_or_empty(self) -> None:
        self.assertEqual(to_timezone_or_empty("America/Denver"), "America/Denver")
        for invalid_timezone in ["invalid/Timezone", "America", "a" * 256]:
            self.assertEqual(to_timezone_or_empty(invalid_timezone), "")

    def test_to_non_negative_int_or_none(self) -> None:
        self.assertEqual(to_non_negative_int_or_none("3"), 3)
        self.assertEqual(to_non_negative_int_or_none("-3"), None)
        self.assertEqual(to_non_negative_int_or_none("a"), None)
        self.assertEqual(to_non_negative_int_or_none("3.5"), None)
        self.assertEqual(to_non_negative_int_or_none("3.0"), None)
        self.assertEqual(to_non_negative_int_or_none("3.1"), None)
        self.assertEqual(to_non_negative_int_or_none("3.9"), None)
        self.assertEqual(to_non_negative_int_or_none("3.5"), None)
        self.assertEqual(to_non_negative_int_or_none("foo"), None)
