from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic_link_util import (
    get_message_link_syntax,
    get_stream_link_syntax,
    get_stream_topic_link_syntax,
)


class TestTopicLinkUtil(ZulipTestCase):
    def test_stream_link_syntax(self) -> None:
        sweden_id = self.make_stream("Sweden").id
        money_id = self.make_stream("$$MONEY$$").id
        md_id = self.make_stream("Markdown [md]").id

        self.assertEqual(get_stream_link_syntax(sweden_id, "Sweden"), "#**Sweden**")

        self.assertEqual(
            get_stream_link_syntax(money_id, "$$MONEY$$"),
            f"[#&#36;&#36;MONEY&#36;&#36;](#narrow/channel/{money_id}-.24.24MONEY.24.24)",
        )

        self.assertEqual(
            get_stream_link_syntax(md_id, "Markdown [md]"),
            f"[#Markdown &#91;md&#93;](#narrow/channel/{md_id}-Markdown-.5Bmd.5D)",
        )

    def test_stream_topic_link_syntax(self) -> None:
        sweden_id = self.make_stream("Sweden").id
        money_id = self.make_stream("$$MONEY$$").id
        denmark_id = self.get_stream_id("Denmark")

        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "topic"), "#**Sweden>topic**"
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "test `test` test"),
            f"[#Sweden > test &#96;test&#96; test](#narrow/channel/{sweden_id}-Sweden/topic/test.20.60test.60.20test)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(denmark_id, "Denmark", "test `test` test`s"),
            f"[#Denmark > test &#96;test&#96; test&#96;s](#narrow/channel/{denmark_id}-Denmark/topic/test.20.60test.60.20test.60s)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "error due to *"),
            f"[#Sweden > error due to &#42;](#narrow/channel/{sweden_id}-Sweden/topic/error.20due.20to.20*)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "*asterisk"),
            f"[#Sweden > &#42;asterisk](#narrow/channel/{sweden_id}-Sweden/topic/*asterisk)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "greaterthan>"),
            f"[#Sweden > greaterthan&gt;](#narrow/channel/{sweden_id}-Sweden/topic/greaterthan.3E)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(money_id, "$$MONEY$$", "dollar"),
            f"[#&#36;&#36;MONEY&#36;&#36; > dollar](#narrow/channel/{money_id}-.24.24MONEY.24.24/topic/dollar)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "swe$$dish"),
            f"[#Sweden > swe&#36;&#36;dish](#narrow/channel/{sweden_id}-Sweden/topic/swe.24.24dish)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "&ab"),
            f"[#Sweden > &amp;ab](#narrow/channel/{sweden_id}-Sweden/topic/.26ab)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "&ab]"),
            f"[#Sweden > &amp;ab&#93;](#narrow/channel/{sweden_id}-Sweden/topic/.26ab.5D)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", "&a[b"),
            f"[#Sweden > &amp;a&#91;b](#narrow/channel/{sweden_id}-Sweden/topic/.26a.5Bb)",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sweden", ""),
            "#**Sweden>**",
        )
        self.assertEqual(
            get_stream_topic_link_syntax(sweden_id, "Sw*den", ""),
            f"[#Sw&#42;den > general chat](#narrow/channel/{sweden_id}-Sw*den/topic/)",
        )

    def test_message_link_syntax(self) -> None:
        sweden_id = self.make_stream("Sweden").id
        self.assertEqual(
            get_message_link_syntax(sweden_id, "Sweden", "topic", 123),
            "#**Sweden>topic@123**",
        )
        self.assertEqual(
            get_message_link_syntax(sweden_id, "Sweden", "", 123),
            "#**Sweden>@123**",
        )
        self.assertEqual(
            get_message_link_syntax(sweden_id, "Sw*den", "topic", 123),
            f"[#Sw&#42;den > topic @ 💬](#narrow/channel/{sweden_id}-Sw*den/topic/topic/near/123)",
        )
        self.assertEqual(
            get_message_link_syntax(sweden_id, "Sw*den", "", 123),
            f"[#Sw&#42;den > general chat @ 💬](#narrow/channel/{sweden_id}-Sw*den/topic//near/123)",
        )
