
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX, is_topic_resolved

class TopicResolutionTest(ZulipTestCase):
    def test_is_topic_resolved(self) -> None:
        self.assertTrue(is_topic_resolved(RESOLVED_TOPIC_PREFIX + "meeting notes"))
        self.assertFalse(is_topic_resolved("meeting notes"))
        self.assertFalse(is_topic_resolved(""))
        self.assertFalse(is_topic_resolved("✔meeting notes"))

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX, is_topic_resolved

class TopicResolutionTest(ZulipTestCase):
    def test_is_topic_resolved(self) -> None:
        self.assertTrue(is_topic_resolved(RESOLVED_TOPIC_PREFIX + "meeting notes"))
        self.assertFalse(is_topic_resolved("meeting notes"))
        self.assertFalse(is_topic_resolved(""))
        self.assertFalse(is_topic_resolved("✔meeting notes"))
