from zerver.context_processors import get_zulip_version_name
from zerver.lib.test_classes import ZulipTestCase


class TestContextProcessors(ZulipTestCase):
    def test_get_zulip_version_name(self) -> None:
        self.assertEqual(get_zulip_version_name("4.0-dev+git"), "Zulip 4.0-dev")
        self.assertEqual(get_zulip_version_name("4.0"), "Zulip 4.0")
