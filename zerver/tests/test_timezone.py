from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timezone import canonicalize_timezone


class TimeZoneTest(ZulipTestCase):
    def test_canonicalize_timezone(self) -> None:
        self.assertEqual(canonicalize_timezone("America/Los_Angeles"), "America/Los_Angeles")
        self.assertEqual(canonicalize_timezone("US/Pacific"), "America/Los_Angeles")
        self.assertEqual(canonicalize_timezone("Gondor/Minas_Tirith"), "Gondor/Minas_Tirith")
