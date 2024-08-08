import zoneinfo
from datetime import datetime

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.typed_endpoint_validators import (
    check_int_in,
    check_string_in,
    check_url,
    convert_to_datetime,
    to_non_negative_int_or_none,
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

    def test_convert_to_datetime(self) -> None:
        UTC = zoneinfo.ZoneInfo("UTC")

        self.assertEqual(convert_to_datetime("2021-06-01"), datetime(2021, 6, 1, tzinfo=UTC))
        self.assertEqual(
            convert_to_datetime("2021-06-01T12:00:00"), datetime(2021, 6, 1, 12, 0, 0, tzinfo=UTC)
        )
        self.assertEqual(
            convert_to_datetime("2021-06-01T12:00:00Z"), datetime(2021, 6, 1, 12, 0, 0, tzinfo=UTC)
        )

        my_dt = datetime(2021, 6, 1, 12, 0, 0, tzinfo=UTC)
        self.assertEqual(convert_to_datetime(int(my_dt.timestamp())), my_dt)

        with self.assertRaisesRegex(ValueError, "Not a valid datetime"):
            convert_to_datetime("random string")

        with self.assertRaisesRegex(ValueError, "Not a valid datetime"):
            convert_to_datetime(["invalid"])
