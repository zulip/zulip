from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import get_topic_resolution_and_bare_name


class TestTopic(ZulipTestCase):
    def test_get_topic_resolution_and_bare_name_resolved(self) -> None:
        resolved, topic = get_topic_resolution_and_bare_name("✔ Fix login bug")
        self.assertTrue(resolved)
        self.assertEqual(topic, "Fix login bug")

    def test_get_topic_resolution_and_bare_name_unresolved(self) -> None:
        resolved, topic = get_topic_resolution_and_bare_name("Fix login bug")
        self.assertFalse(resolved)
        self.assertEqual(topic, "Fix login bug")
