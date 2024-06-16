from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.typed_endpoint_validators import check_int_in, check_url


class ValidatorTestCase(ZulipTestCase):
    def test_check_int_in(self) -> None:
        check_int_in(3, [1, 2, 3])
        with self.assertRaisesRegex(ValueError, "Not in the list of possible values"):
            check_int_in(3, [1, 2])

    def test_check_url(self) -> None:
        check_url("https://example.com")
        with self.assertRaisesRegex(ValueError, "Not a URL"):
            check_url("https://127.0.0..:5000")
