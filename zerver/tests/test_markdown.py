import copy
import os
import re
from html import escape
from textwrap import dedent
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest import mock

import orjson
import requests
import responses
from bs4 import BeautifulSoup
from django.conf import settings
from django.test import override_settings
from markdown import Markdown
from responses import matchers
from typing_extensions import override

from zerver.actions.alert_words import do_add_alert_words
from zerver.actions.create_realm import do_create_realm
from zerver.actions.realm_emoji import do_remove_realm_emoji
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import change_user_is_active
from zerver.lib.alert_words import get_alert_word_automaton
from zerver.lib.camo import get_camo_url
from zerver.lib.create_user import create_user
from zerver.lib.emoji import codepoint_to_name, get_emoji_url
from zerver.lib.emoji_utils import hex_codepoint_to_emoji
from zerver.lib.exceptions import JsonableError, MarkdownRenderingError
from zerver.lib.markdown import (
    POSSIBLE_EMOJI_RE,
    InlineInterestingLinkProcessor,
    MarkdownListPreprocessor,
    MessageRenderingResult,
    clear_state_for_testing,
    content_has_emoji_syntax,
    fetch_tweet_data,
    get_tweet_id,
    image_preview_enabled,
    markdown_convert,
    maybe_update_markdown_engines,
    possible_linked_stream_names,
    render_message_markdown,
    topic_links,
    url_embed_preview_enabled,
    url_to_a,
)
from zerver.lib.markdown.fenced_code import FencedBlockPreprocessor
from zerver.lib.mdiff import diff_strings
from zerver.lib.mention import (
    FullNameInfo,
    MentionBackend,
    MentionData,
    PossibleMentions,
    get_possible_mentions_info,
    possible_mentions,
    possible_user_group_mentions,
    stream_wildcards,
    topic_wildcards,
)
from zerver.lib.per_request_cache import flush_per_request_caches
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.tex import render_tex
from zerver.models import Message, NamedUserGroup, RealmEmoji, RealmFilter, UserMessage, UserProfile
from zerver.models.clients import get_client
from zerver.models.groups import SystemGroups
from zerver.models.linkifiers import linkifiers_for_realm
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream


class SimulatedFencedBlockPreprocessor(FencedBlockPreprocessor):
    # Simulate code formatting.

    @override
    def format_code(self, lang: Optional[str], code: str) -> str:
        return (lang or "") + ":" + code

    @override
    def placeholder(self, s: str) -> str:
        return "**" + s.strip("\n") + "**"


class FencedBlockPreprocessorTest(ZulipTestCase):
    def test_simple_quoting(self) -> None:
        processor = FencedBlockPreprocessor(Markdown())
        markdown_input = [
            "~~~ quote",
            "hi",
            "bye",
            "",
            "",
        ]
        expected = [
            "",
            "> hi",
            "> bye",
            "> ",
            "> ",
            "",
            "",
        ]
        lines = processor.run(markdown_input)
        self.assertEqual(lines, expected)

    def test_serial_quoting(self) -> None:
        processor = FencedBlockPreprocessor(Markdown())
        markdown_input = [
            "~~~ quote",
            "hi",
            "~~~",
            "",
            "~~~ quote",
            "bye",
            "",
            "",
        ]
        expected = [
            "",
            "> hi",
            "",
            "",
            "",
            "> bye",
            "> ",
            "> ",
            "",
            "",
        ]
        lines = processor.run(markdown_input)
        self.assertEqual(lines, expected)

    def test_serial_code(self) -> None:
        processor = SimulatedFencedBlockPreprocessor(Markdown())

        markdown_input = [
            "``` .py",
            "hello()",
            "```",
            "",
            "```vb.net",
            "goodbye()",
            "```",
            "",
            "```c#",
            "weirdchar()",
            "```",
            "",
            "```",
            "no-highlight()",
            "```",
            "",
        ]
        expected = [
            "",
            "**py:hello()**",
            "",
            "",
            "",
            "**vb.net:goodbye()**",
            "",
            "",
            "",
            "**c#:weirdchar()**",
            "",
            "",
            "",
            "**:no-highlight()**",
            "",
            "",
        ]
        lines = processor.run(markdown_input)
        self.assertEqual(lines, expected)

    def test_nested_code(self) -> None:
        processor = SimulatedFencedBlockPreprocessor(Markdown())

        markdown_input = [
            "~~~ quote",
            "hi",
            "``` .py",
            "hello()",
            "```",
            "",
            "",
        ]
        expected = [
            "",
            "> hi",
            "> ",
            "> **py:hello()**",
            "> ",
            "> ",
            "> ",
            "",
            "",
        ]
        lines = processor.run(markdown_input)
        self.assertEqual(lines, expected)


def markdown_convert_wrapper(content: str) -> str:
    return markdown_convert(
        content=content,
        message_realm=get_realm("zulip"),
    ).rendered_content


class MarkdownMiscTest(ZulipTestCase):
    def test_diffs_work_as_expected(self) -> None:
        str1 = "<p>The quick brown fox jumps over the lazy dog.  Animal stories are fun, yeah</p>"
        str2 = "<p>The fast fox jumps over the lazy dogs and cats.  Animal stories are fun</p>"
        expected_diff = "\u001b[34m-\u001b[0m <p>The \u001b[33mquick brown\u001b[0m fox jumps over the lazy dog.  Animal stories are fun\u001b[31m, yeah\u001b[0m</p>\n\u001b[34m+\u001b[0m <p>The \u001b[33mfast\u001b[0m fox jumps over the lazy dog\u001b[32ms and cats\u001b[0m.  Animal stories are fun</p>\n"
        self.assertEqual(diff_strings(str1, str2), expected_diff)

    def test_get_possible_mentions_info(self) -> None:
        realm = get_realm("zulip")

        def make_user(email: str, full_name: str) -> UserProfile:
            return create_user(
                email=email,
                password="whatever",
                realm=realm,
                full_name=full_name,
            )

        fred1 = make_user("fred1@example.com", "Fred Flintstone")
        change_user_is_active(fred1, False)

        fred2 = make_user("fred2@example.com", "Fred Flintstone")

        fred3 = make_user("fred3@example.com", "Fred Flintstone")
        change_user_is_active(fred3, False)

        fred4 = make_user("fred4@example.com", "Fred Flintstone")

        mention_backend = MentionBackend(realm.id)
        lst = get_possible_mentions_info(
            mention_backend,
            {"Fred Flintstone", "Cordelia, LEAR's daughter", "Not A User"},
            message_sender=None,
        )
        set_of_names = {x.full_name.lower() for x in lst}
        self.assertEqual(set_of_names, {"fred flintstone", "cordelia, lear's daughter"})

        by_id = {row.id: row for row in lst}
        self.assertEqual(
            by_id.get(fred2.id),
            FullNameInfo(
                full_name="Fred Flintstone",
                id=fred2.id,
                is_active=True,
            ),
        )
        self.assertEqual(
            by_id.get(fred4.id),
            FullNameInfo(
                full_name="Fred Flintstone",
                id=fred4.id,
                is_active=True,
            ),
        )

    def test_mention_data(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        content = "@**King Hamlet** @**Cordelia, lear's daughter**"
        mention_backend = MentionBackend(realm.id)
        mention_data = MentionData(mention_backend, content, message_sender=None)
        self.assertEqual(mention_data.get_user_ids(), {hamlet.id, cordelia.id})
        self.assertEqual(
            mention_data.get_user_by_id(hamlet.id),
            FullNameInfo(
                full_name=hamlet.full_name,
                id=hamlet.id,
                is_active=True,
            ),
        )

        user = mention_data.get_user_by_name("king hamLET")
        assert user is not None
        self.assertEqual(user.full_name, hamlet.full_name)

        self.assertFalse(mention_data.message_has_stream_wildcards())
        content = "@**King Hamlet** @**Cordelia, lear's daughter** @**all**"
        mention_data = MentionData(mention_backend, content, message_sender=None)
        self.assertTrue(mention_data.message_has_stream_wildcards())

        self.assertFalse(mention_data.message_has_topic_wildcards())
        content = "@**King Hamlet** @**Cordelia, lear's daughter** @**topic**"
        mention_data = MentionData(mention_backend, content, message_sender=None)
        self.assertTrue(mention_data.message_has_topic_wildcards())

    def test_invalid_katex_path(self) -> None:
        with self.settings(DEPLOY_ROOT="/nonexistent"):
            with self.assertLogs(level="ERROR") as m:
                render_tex("random text")
            self.assertEqual(m.output, ["ERROR:root:Cannot find KaTeX for latex rendering!"])

    @responses.activate
    @override_settings(KATEX_SERVER=True, SHARED_SECRET="foo")
    def test_katex_server(self) -> None:
        responses.post(
            "http://localhost:9700/",
            match=[
                matchers.urlencoded_params_matcher(
                    {"content": "foo", "is_display": "false", "shared_secret": "foo"}
                )
            ],
            content_type="text/html; charset=utf-8",
            body="<i>html</i>",
        )
        self.assertEqual(render_tex("foo"), "<i>html</i>")

        responses.post(
            "http://localhost:9700/?",
            match=[
                matchers.urlencoded_params_matcher(
                    {"content": "foo", "is_display": "true", "shared_secret": "foo"}
                )
            ],
            content_type="text/html; charset=utf-8",
            body="<i>other</i>",
        )
        self.assertEqual(render_tex("foo", is_inline=False), "<i>other</i>")

        responses.post(
            "http://localhost:9700/",
            content_type="text/html; charset=utf-8",
            status=400,
            body=r"KaTeX parse error: &#39;\&#39;",
        )
        self.assertEqual(render_tex("bad"), None)

        responses.post(
            "http://localhost:9700/",
            content_type="text/html; charset=utf-8",
            status=400,
            body=r"KaTeX parse error: &#39;\&#39;",
        )
        self.assertEqual(render_tex("bad"), None)

        responses.post("http://localhost:9700/", status=403, body="")
        with self.assertLogs(level="WARNING") as m:
            self.assertEqual(render_tex("bad"), None)
        self.assertEqual(m.output, ["WARNING:root:KaTeX rendering service failed: (403) "])

        responses.post("http://localhost:9700/", status=500, body="")
        with self.assertLogs(level="WARNING") as m:
            self.assertEqual(render_tex("bad"), None)
        self.assertEqual(m.output, ["WARNING:root:KaTeX rendering service failed: (500) "])

        responses.post("http://localhost:9700/", body=requests.exceptions.Timeout())
        with self.assertLogs(level="WARNING") as m:
            self.assertEqual(render_tex("bad"), None)
        self.assertEqual(
            m.output, ["WARNING:root:KaTeX rendering service timed out with 3 byte long input"]
        )

        responses.post("http://localhost:9700/", body=requests.exceptions.ConnectionError())
        with self.assertLogs(level="WARNING") as m:
            self.assertEqual(render_tex("bad"), None)
        self.assertEqual(m.output, ["WARNING:root:KaTeX rendering service failed: ConnectionError"])

        with override_settings(KATEX_SERVER_PORT=9701):
            responses.post(
                "http://localhost:9701/",
                body="<i>html</i>",
                content_type="text/html; charset=utf-8",
            )
            self.assertEqual(render_tex("foo"), "<i>html</i>")


class MarkdownListPreprocessorTest(ZulipTestCase):
    # We test that the preprocessor inserts blank lines at correct places.
    # We use <> to indicate that we need to insert a blank line here.
    def split_message(self, msg: str) -> Tuple[List[str], List[str]]:
        original = msg.replace("<>", "").split("\n")
        expected = re.split(r"\n|<>", msg)
        return original, expected

    def test_basic_list(self) -> None:
        preprocessor = MarkdownListPreprocessor()
        original, expected = self.split_message("List without a gap\n<>* One\n* Two")
        self.assertEqual(preprocessor.run(original), expected)

    def test_list_after_quotes(self) -> None:
        preprocessor = MarkdownListPreprocessor()
        original, expected = self.split_message(
            "```quote\nSomething\n```\n\nList without a gap\n<>* One\n* Two"
        )
        self.assertEqual(preprocessor.run(original), expected)

    def test_list_in_code(self) -> None:
        preprocessor = MarkdownListPreprocessor()
        original, expected = self.split_message("```\nList without a gap\n* One\n* Two\n```")
        self.assertEqual(preprocessor.run(original), expected)

    def test_complex_nesting_with_different_fences(self) -> None:
        preprocessor = MarkdownListPreprocessor()
        msg = """```quote
In quote. We should convert a list here:<>
* one
* two

~~~
This is a nested code fence, do not make changes here:
* one
* two

````quote
Quote in code fence. Should not convert:
* one
* two
````

~~~

Back in the quote. We should convert:<>
* one
* two
```

Outside. Should convert:<>
* one
* two
        """
        original, expected = self.split_message(msg)
        self.assertEqual(preprocessor.run(original), expected)

    def test_complex_nesting_with_same_fence(self) -> None:
        preprocessor = MarkdownListPreprocessor()
        msg = """```quote
In quote. We should convert a list here:<>
* one
* two

```python
This is a nested code fence, do not make changes here:
* one
* two

```quote
Quote in code fence. Should not convert:
* one
* two
```

```

Back in the quote. We should convert:<>
* one
* two
```

Outside. Should convert:<>
* one
* two
        """
        original, expected = self.split_message(msg)
        self.assertEqual(preprocessor.run(original), expected)


class MarkdownTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        clear_state_for_testing()

    @override
    def assertEqual(self, first: Any, second: Any, msg: str = "") -> None:
        if isinstance(first, str) and isinstance(second, str):
            if first != second:
                raise AssertionError(
                    "Actual and expected outputs do not match; showing diff.\n"
                    + diff_strings(first, second)
                    + msg
                )
        else:
            super().assertEqual(first, second)

    def load_markdown_tests(self) -> Tuple[Dict[str, Any], List[List[str]]]:
        test_fixtures = {}
        with open(
            os.path.join(os.path.dirname(__file__), "fixtures/markdown_test_cases.json"), "rb"
        ) as f:
            data = orjson.loads(f.read())
        for test in data["regular_tests"]:
            test_fixtures[test["name"]] = test

        return test_fixtures, data["linkify_tests"]

    def test_markdown_no_ignores(self) -> None:
        # We do not want any ignored tests to be committed and merged.
        format_tests, linkify_tests = self.load_markdown_tests()
        for name, test in format_tests.items():
            message = f'Test "{name}" shouldn\'t be ignored.'
            is_ignored = test.get("ignore", False)
            self.assertFalse(is_ignored, message)

    def test_markdown_fixtures_unique_names(self) -> None:
        # All markdown fixtures must have unique names.
        found_names: Set[str] = set()
        with open(
            os.path.join(os.path.dirname(__file__), "fixtures/markdown_test_cases.json"), "rb"
        ) as f:
            data = orjson.loads(f.read())
        for test in data["regular_tests"]:
            test_name = test["name"]
            message = f'Test name: "{test_name}" must be unique.'
            is_unique = test_name not in found_names
            self.assertTrue(is_unique, message)
            found_names.add(test_name)

    @override_settings(THUMBNAIL_IMAGES=True)
    def test_markdown_fixtures(self) -> None:
        format_tests, linkify_tests = self.load_markdown_tests()
        valid_keys = {
            "name",
            "input",
            "expected_output",
            "backend_only_rendering",
            "marked_expected_output",
            "text_content",
            "translate_emoticons",
            "ignore",
        }

        for name, test in format_tests.items():
            with self.subTest(markdown_test_case=name):
                # Check that there aren't any unexpected keys as those are often typos
                self.assert_length(set(test.keys()) - valid_keys, 0)
                # Ignore tests if specified
                if test.get("ignore", False):
                    continue  # nocoverage

                if test.get("translate_emoticons", False):
                    # Create a userprofile and send message with it.
                    user_profile = self.example_user("othello")
                    do_change_user_setting(
                        user_profile, "translate_emoticons", True, acting_user=None
                    )
                    msg = Message(
                        sender=user_profile,
                        sending_client=get_client("test"),
                        realm=user_profile.realm,
                    )
                    rendering_result = render_message_markdown(msg, test["input"])
                    converted = rendering_result.rendered_content
                else:
                    converted = markdown_convert_wrapper(test["input"])

                self.assertEqual(converted, test["expected_output"])

        def replaced(payload: str, url: str, phrase: str = "") -> str:
            if url[:4] == "http":
                href = url
            elif "@" in url:
                href = "mailto:" + url
            else:
                href = "http://" + url
            return payload % (f'<a href="{href}">{url}</a>',)

        for inline_url, reference, url in linkify_tests:
            try:
                match = replaced(reference, url, phrase=inline_url)
            except TypeError:
                match = reference
            converted = markdown_convert_wrapper(inline_url)
            self.assertEqual(match, converted)

    def test_inline_file(self) -> None:
        msg = "Check out this file file:///Volumes/myserver/Users/Shared/pi.py"
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            '<p>Check out this file <a href="file:///Volumes/myserver/Users/Shared/pi.py">file:///Volumes/myserver/Users/Shared/pi.py</a></p>',
        )

        clear_state_for_testing()
        with self.settings(ENABLE_FILE_LINKS=False):
            realm = do_create_realm(string_id="file_links_test", name="file_links_test")
            maybe_update_markdown_engines(realm.id, False)
            self.assertEqual(
                markdown_convert(msg, message_realm=realm).rendered_content,
                "<p>Check out this file file:///Volumes/myserver/Users/Shared/pi.py</p>",
            )

    def test_inline_bitcoin(self) -> None:
        msg = "To bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or not to bitcoin"
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            '<p>To <a href="bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa">bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa</a> or not to bitcoin</p>',
        )

    def test_inline_youtube(self) -> None:
        msg = "Check out the debate: http://www.youtube.com/watch?v=hx1mjT73xYE"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="youtube-video message_inline_image"><a data-id="hx1mjT73xYE" href="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="{get_camo_url("https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg")}"></a></div>""",
        )

        msg = "http://www.youtube.com/watch?v=hx1mjT73xYE"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="youtube-video message_inline_image"><a data-id="hx1mjT73xYE" href="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="{get_camo_url("https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg")}"></a></div>""",
        )

        msg = "https://youtu.be/hx1mjT73xYE"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="https://youtu.be/hx1mjT73xYE">https://youtu.be/hx1mjT73xYE</a></p>\n<div class="youtube-video message_inline_image"><a data-id="hx1mjT73xYE" href="https://youtu.be/hx1mjT73xYE"><img src="{get_camo_url("https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg")}"></a></div>""",
        )

        msg = "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo"
        not_converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            not_converted,
            '<p><a href="https://www.youtube.com/playlist?list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo">https://www.youtube.com/playlist?list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo</a></p>',
        )

        msg = "https://www.youtube.com/watch?v=O5nskjZ_GoI&list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="https://www.youtube.com/watch?v=O5nskjZ_GoI&amp;list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo">https://www.youtube.com/watch?v=O5nskjZ_GoI&amp;list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo</a></p>\n<div class="youtube-video message_inline_image"><a data-id="O5nskjZ_GoI" href="https://www.youtube.com/watch?v=O5nskjZ_GoI&amp;list=PL8dPuuaLjXtNlUrzyH5r6jN9ulIgZBpdo"><img src="{get_camo_url("https://i.ytimg.com/vi/O5nskjZ_GoI/default.jpg")}"></a></div>""",
        )

        msg = "http://www.youtube.com/watch_videos?video_ids=nOJgD4fcZhI,i96UO8-GFvw"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="http://www.youtube.com/watch_videos?video_ids=nOJgD4fcZhI,i96UO8-GFvw">http://www.youtube.com/watch_videos?video_ids=nOJgD4fcZhI,i96UO8-GFvw</a></p>\n<div class="youtube-video message_inline_image"><a data-id="nOJgD4fcZhI" href="http://www.youtube.com/watch_videos?video_ids=nOJgD4fcZhI,i96UO8-GFvw"><img src="{get_camo_url("https://i.ytimg.com/vi/nOJgD4fcZhI/default.jpg")}"></a></div>""",
        )

    @override_settings(INLINE_URL_EMBED_PREVIEW=False)
    def test_inline_vimeo(self) -> None:
        msg = "Check out the debate: https://vimeo.com/246979354"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            '<p>Check out the debate: <a href="https://vimeo.com/246979354">https://vimeo.com/246979354</a></p>',
        )

        msg = "https://vimeo.com/246979354"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            '<p><a href="https://vimeo.com/246979354">https://vimeo.com/246979354</a></p>',
        )

    @override_settings(THUMBNAIL_IMAGES=True, INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_thumbnail_url(self) -> None:
        realm = get_realm("zephyr")
        msg = "[foobar](/user_uploads/{realm_id}/50/w2G6ok9kr8AMCQCTNAUOFMln/IMG_0677.JPG)"
        msg = msg.format(realm_id=realm.id)
        thumbnail_img = '<img data-src-fullsize="/thumbnail?url=user_uploads%2F{realm_id}%2F50%2Fw2G6ok9kr8AMCQCTNAUOFMln%2FIMG_0677.JPG&amp;size=full" src="/thumbnail?url=user_uploads%2F{realm_id}%2F50%2Fw2G6ok9kr8AMCQCTNAUOFMln%2FIMG_0677.JPG&amp;size=thumbnail"><'
        thumbnail_img = thumbnail_img.format(realm_id=realm.id)
        converted = markdown_convert_wrapper(msg)
        self.assertIn(thumbnail_img, converted)

        msg = "https://www.google.com/images/srpr/logo4w.png"
        thumbnail_img = '<img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=thumbnail">'
        converted = markdown_convert_wrapper(msg)
        self.assertIn(thumbnail_img, converted)

        msg = "www.google.com/images/srpr/logo4w.png"
        thumbnail_img = '<img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=thumbnail">'
        converted = markdown_convert_wrapper(msg)
        self.assertIn(thumbnail_img, converted)

        msg = "https://www.google.com/images/srpr/logo4w.png"
        thumbnail_img = f"""<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png"><img src="{get_camo_url("https://www.google.com/images/srpr/logo4w.png")}"></a></div>"""
        with self.settings(THUMBNAIL_IMAGES=False):
            converted = markdown_convert_wrapper(msg)
        self.assertIn(thumbnail_img, converted)

        # Any URL which is not an external link and doesn't start with
        # /user_uploads/ is not thumbnailed
        msg = "[foobar](/static/images/cute/turtle.png)"
        thumbnail_img = '<div class="message_inline_image"><a href="/static/images/cute/turtle.png" title="foobar"><img src="/static/images/cute/turtle.png"></a></div>'
        converted = markdown_convert_wrapper(msg)
        self.assertIn(thumbnail_img, converted)

        msg = "[foobar](/user_avatars/{realm_id}/emoji/images/50.png)"
        msg = msg.format(realm_id=realm.id)
        thumbnail_img = '<div class="message_inline_image"><a href="/user_avatars/{realm_id}/emoji/images/50.png" title="foobar"><img src="/user_avatars/{realm_id}/emoji/images/50.png"></a></div>'
        thumbnail_img = thumbnail_img.format(realm_id=realm.id)
        converted = markdown_convert_wrapper(msg)
        self.assertIn(thumbnail_img, converted)

    @override_settings(THUMBNAIL_IMAGES=True, INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_preview(self) -> None:
        with_preview = '<div class="message_inline_image"><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fcdn.wallpapersafari.com%2F13%2F6%2F16eVjx.jpeg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fcdn.wallpapersafari.com%2F13%2F6%2F16eVjx.jpeg&amp;size=thumbnail"></a></div>'
        without_preview = '<p><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg">http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg</a></p>'
        content = "http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg"

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, with_preview)

        realm = msg.get_realm()
        realm.inline_image_preview = False
        realm.save()

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, without_preview)

    @override_settings(EXTERNAL_URI_SCHEME="https://")
    def test_external_image_preview_use_camo(self) -> None:
        content = "https://example.com/thing.jpeg"

        thumbnail_img = f"""<div class="message_inline_image"><a href="{content}"><img src="{get_camo_url(content)}"></a></div>"""
        converted = markdown_convert_wrapper(content)
        self.assertIn(converted, thumbnail_img)

    @override_settings(EXTERNAL_URI_SCHEME="https://")
    def test_static_image_preview_skip_camo(self) -> None:
        content = f"{ settings.STATIC_URL }/thing.jpeg"

        thumbnail_img = f"""<div class="message_inline_image"><a href="{content}"><img src="{content}"></a></div>"""
        converted = markdown_convert_wrapper(content)
        self.assertIn(converted, thumbnail_img)

    @override_settings(EXTERNAL_URI_SCHEME="https://")
    def test_realm_image_preview_skip_camo(self) -> None:
        content = f"https://zulip.{ settings.EXTERNAL_HOST }/thing.jpeg"
        converted = markdown_convert_wrapper(content)
        self.assertNotIn(converted, get_camo_url(content))

    @override_settings(EXTERNAL_URI_SCHEME="https://")
    def test_cross_realm_image_preview_use_camo(self) -> None:
        content = f"https://otherrealm.{ settings.EXTERNAL_HOST }/thing.jpeg"

        thumbnail_img = f"""<div class="message_inline_image"><a href="{ content }"><img src="{ get_camo_url(content) }"></a></div>"""
        converted = markdown_convert_wrapper(content)
        self.assertIn(converted, thumbnail_img)

    @override_settings(INLINE_IMAGE_PREVIEW=True)
    def test_max_inline_preview(self) -> None:
        image_links = [
            # Add a youtube link within a spoiler to ensure other link types are counted
            """```spoiler Check out this PyCon video\nhttps://www.youtube.com/watch?v=0c46YHS3RY8\n```""",
            # Add a link within blockquote to test that it does NOT get counted
            "> http://cdn.wallpapersafari.com/spoiler/dont_count.jpeg\n",
            # Using INLINE_PREVIEW_LIMIT_PER_MESSAGE - 1 because of the one link in a spoiler added already
            *(
                f"http://cdn.wallpapersafari.com/{x}/6/16eVjx.jpeg"
                for x in range(InlineInterestingLinkProcessor.INLINE_PREVIEW_LIMIT_PER_MESSAGE - 1)
            ),
        ]
        within_limit_content = "\n".join(image_links)
        above_limit_content = (
            within_limit_content + "\nhttp://cdn.wallpapersafari.com/above/0/6/16eVjx.jpeg"
        )

        # When the number of image links is within the preview limit, the
        # output should contain the same number of inline images.
        converted = markdown_convert_wrapper(within_limit_content)
        soup = BeautifulSoup(converted, "html.parser")
        self.assert_length(
            soup(class_="message_inline_image"),
            InlineInterestingLinkProcessor.INLINE_PREVIEW_LIMIT_PER_MESSAGE,
        )

        # When the number of image links is over the limit, then there should
        # be zero inline images.
        converted = markdown_convert_wrapper(above_limit_content)
        soup = BeautifulSoup(converted, "html.parser")
        self.assert_length(soup(class_="message_inline_image"), 0)

    @override_settings(THUMBNAIL_IMAGES=True, INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_quoted_blocks(self) -> None:
        content = "http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg"
        expected = '<div class="message_inline_image"><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fcdn.wallpapersafari.com%2F13%2F6%2F16eVjx.jpeg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fcdn.wallpapersafari.com%2F13%2F6%2F16eVjx.jpeg&amp;size=thumbnail"></a></div>'
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

        content = ">http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg\n\nAwesome!"
        expected = '<blockquote>\n<p><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg">http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg</a></p>\n</blockquote>\n<p>Awesome!</p>'
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

        content = ">* http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg\n\nAwesome!"
        expected = '<blockquote>\n<ul>\n<li><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg">http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg</a></li>\n</ul>\n</blockquote>\n<p>Awesome!</p>'
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

    @override_settings(THUMBNAIL_IMAGES=True, INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_preview_order(self) -> None:
        realm = get_realm("zulip")
        content = "http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg\nhttp://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg\nhttp://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg"
        expected = '<p><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg</a><br>\n<a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg</a><br>\n<a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg</a></p>\n<div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=thumbnail"></a></div><div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_02.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_02.jpg&amp;size=thumbnail"></a></div><div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=thumbnail"></a></div>'

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

        content = "http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg\n\n>http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg\n\n* http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg\n* https://www.google.com/images/srpr/logo4w.png"
        expected = '<div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=thumbnail"></a></div><blockquote>\n<p><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg</a></p>\n</blockquote>\n<ul>\n<li><div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=thumbnail"></a></div></li>\n<li><div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=thumbnail"></a></div></li>\n</ul>'

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

        content = "Test 1\n[21136101110_1dde1c1a7e_o.jpg](/user_uploads/{realm_id}/6d/F1PX6u16JA2P-nK45PyxHIYZ/21136101110_1dde1c1a7e_o.jpg) \n\nNext image\n[IMG_20161116_023910.jpg](/user_uploads/{realm_id}/69/sh7L06e7uH7NaX6d5WFfVYQp/IMG_20161116_023910.jpg) \n\nAnother screenshot\n[Screenshot-from-2016-06-01-16-22-42.png](/user_uploads/{realm_id}/70/_aZmIEWaN1iUaxwkDjkO7bpj/Screenshot-from-2016-06-01-16-22-42.png)"
        content = content.format(realm_id=realm.id)
        expected = '<p>Test 1<br>\n<a href="/user_uploads/{realm_id}/6d/F1PX6u16JA2P-nK45PyxHIYZ/21136101110_1dde1c1a7e_o.jpg">21136101110_1dde1c1a7e_o.jpg</a> </p>\n<div class="message_inline_image"><a href="/user_uploads/{realm_id}/6d/F1PX6u16JA2P-nK45PyxHIYZ/21136101110_1dde1c1a7e_o.jpg" title="21136101110_1dde1c1a7e_o.jpg"><img data-src-fullsize="/thumbnail?url=user_uploads%2F{realm_id}%2F6d%2FF1PX6u16JA2P-nK45PyxHIYZ%2F21136101110_1dde1c1a7e_o.jpg&amp;size=full" src="/thumbnail?url=user_uploads%2F{realm_id}%2F6d%2FF1PX6u16JA2P-nK45PyxHIYZ%2F21136101110_1dde1c1a7e_o.jpg&amp;size=thumbnail"></a></div><p>Next image<br>\n<a href="/user_uploads/{realm_id}/69/sh7L06e7uH7NaX6d5WFfVYQp/IMG_20161116_023910.jpg">IMG_20161116_023910.jpg</a> </p>\n<div class="message_inline_image"><a href="/user_uploads/{realm_id}/69/sh7L06e7uH7NaX6d5WFfVYQp/IMG_20161116_023910.jpg" title="IMG_20161116_023910.jpg"><img data-src-fullsize="/thumbnail?url=user_uploads%2F{realm_id}%2F69%2Fsh7L06e7uH7NaX6d5WFfVYQp%2FIMG_20161116_023910.jpg&amp;size=full" src="/thumbnail?url=user_uploads%2F{realm_id}%2F69%2Fsh7L06e7uH7NaX6d5WFfVYQp%2FIMG_20161116_023910.jpg&amp;size=thumbnail"></a></div><p>Another screenshot<br>\n<a href="/user_uploads/{realm_id}/70/_aZmIEWaN1iUaxwkDjkO7bpj/Screenshot-from-2016-06-01-16-22-42.png">Screenshot-from-2016-06-01-16-22-42.png</a></p>\n<div class="message_inline_image"><a href="/user_uploads/{realm_id}/70/_aZmIEWaN1iUaxwkDjkO7bpj/Screenshot-from-2016-06-01-16-22-42.png" title="Screenshot-from-2016-06-01-16-22-42.png"><img data-src-fullsize="/thumbnail?url=user_uploads%2F{realm_id}%2F70%2F_aZmIEWaN1iUaxwkDjkO7bpj%2FScreenshot-from-2016-06-01-16-22-42.png&amp;size=full" src="/thumbnail?url=user_uploads%2F{realm_id}%2F70%2F_aZmIEWaN1iUaxwkDjkO7bpj%2FScreenshot-from-2016-06-01-16-22-42.png&amp;size=thumbnail"></a></div>'
        expected = expected.format(realm_id=realm.id)

        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

    @override_settings(THUMBNAIL_IMAGES=True, INLINE_IMAGE_PREVIEW=True)
    def test_corrected_image_source(self) -> None:
        # testing only Wikipedia because linx.li URLs can be expected to expire
        content = "https://en.wikipedia.org/wiki/File:Wright_of_Derby,_The_Orrery.jpg"
        expected = '<div class="message_inline_image"><a href="https://en.wikipedia.org/wiki/Special:FilePath/File:Wright_of_Derby,_The_Orrery.jpg"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FSpecial%3AFilePath%2FFile%3AWright_of_Derby%2C_The_Orrery.jpg&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FSpecial%3AFilePath%2FFile%3AWright_of_Derby%2C_The_Orrery.jpg&amp;size=thumbnail"></a></div>'

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

        content = "https://en.wikipedia.org/static/images/icons/wikipedia.png"
        expected = '<div class="message_inline_image"><a href="https://en.wikipedia.org/static/images/icons/wikipedia.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fen.wikipedia.org%2Fstatic%2Fimages%2Ficons%2Fwikipedia.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fen.wikipedia.org%2Fstatic%2Fimages%2Ficons%2Fwikipedia.png&amp;size=thumbnail"></a></div>'
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

    @override_settings(INLINE_IMAGE_PREVIEW=False)
    def test_image_preview_enabled(self) -> None:
        ret = image_preview_enabled()
        self.assertFalse(ret)

        settings.INLINE_IMAGE_PREVIEW = True

        sender_user_profile = self.example_user("othello")
        message = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm = message.get_realm()

        ret = image_preview_enabled()
        self.assertTrue(ret)

        ret = image_preview_enabled(no_previews=True)
        self.assertFalse(ret)

        ret = image_preview_enabled(message, realm)
        self.assertTrue(ret)

        ret = image_preview_enabled(message)
        self.assertTrue(ret)

        ret = image_preview_enabled(message, realm, no_previews=True)
        self.assertFalse(ret)

        ret = image_preview_enabled(message, no_previews=True)
        self.assertFalse(ret)

    @override_settings(INLINE_URL_EMBED_PREVIEW=False)
    def test_url_embed_preview_enabled(self) -> None:
        sender_user_profile = self.example_user("othello")
        message = copy.deepcopy(
            Message(
                sender=sender_user_profile,
                sending_client=get_client("test"),
                realm=sender_user_profile.realm,
            )
        )
        realm = message.get_realm()
        realm.inline_url_embed_preview = True  # off by default
        realm.save(update_fields=["inline_url_embed_preview"])

        ret = url_embed_preview_enabled()
        self.assertFalse(ret)

        settings.INLINE_URL_EMBED_PREVIEW = True

        ret = url_embed_preview_enabled()
        self.assertTrue(ret)

        ret = image_preview_enabled(no_previews=True)
        self.assertFalse(ret)

        ret = url_embed_preview_enabled(message, realm)
        self.assertTrue(ret)
        ret = url_embed_preview_enabled(message)
        self.assertTrue(ret)

        ret = url_embed_preview_enabled(message, no_previews=True)
        self.assertFalse(ret)

    def test_inline_dropbox(self) -> None:
        msg = "Look at how hilarious our old office was: https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG"
        image_info = {
            "image": "https://photos-4.dropbox.com/t/2/AABIre1oReJgPYuc_53iv0IHq1vUzRaDg2rrCfTpiWMccQ/12/129/jpeg/1024x1024/2/_/0/4/IMG_0923.JPG/CIEBIAEgAiAHKAIoBw/ymdijjcg67hv2ta/AABz2uuED1ox3vpWWvMpBxu6a/IMG_0923.JPG",
            "desc": "Shared with Dropbox",
            "title": "IMG_0923.JPG",
        }
        with mock.patch("zerver.lib.markdown.fetch_open_graph_image", return_value=image_info):
            converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p>Look at how hilarious our old office was: <a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG">https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" title="IMG_0923.JPG"><img src="{get_camo_url("https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG?raw=1")}"></a></div>""",
        )

        msg = "Look at my hilarious drawing folder: https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl="
        image_info = {
            "image": "https://cf.dropboxstatic.com/static/images/icons128/folder_dropbox.png",
            "desc": "Shared with Dropbox",
            "title": "Saves",
        }
        with mock.patch("zerver.lib.markdown.fetch_open_graph_image", return_value=image_info):
            converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p>Look at my hilarious drawing folder: <a href="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=">https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=</a></p>\n<div class="message_inline_ref"><a href="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=" title="Saves"><img src="{get_camo_url("https://cf.dropboxstatic.com/static/images/icons128/folder_dropbox.png")}"></a><div><div class="message_inline_image_title">Saves</div><desc class="message_inline_image_desc"></desc></div></div>""",
        )

    def test_inline_dropbox_preview(self) -> None:
        # Test photo album previews
        msg = "https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5"
        image_info = {
            "image": "https://photos-6.dropbox.com/t/2/AAAlawaeD61TyNewO5vVi-DGf2ZeuayfyHFdNTNzpGq-QA/12/271544745/jpeg/1024x1024/2/_/0/5/baby-piglet.jpg/CKnjvYEBIAIgBygCKAc/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0",
            "desc": "Shared with Dropbox",
            "title": "1 photo",
        }
        with mock.patch("zerver.lib.markdown.fetch_open_graph_image", return_value=image_info):
            converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5">https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" title="1 photo"><img src="{get_camo_url("https://photos-6.dropbox.com/t/2/AAAlawaeD61TyNewO5vVi-DGf2ZeuayfyHFdNTNzpGq-QA/12/271544745/jpeg/1024x1024/2/_/0/5/baby-piglet.jpg/CKnjvYEBIAIgBygCKAc/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0")}"></a></div>""",
        )

    @override_settings(THUMBNAIL_IMAGES=True)
    def test_inline_dropbox_negative(self) -> None:
        # Make sure we're not overzealous in our conversion:
        msg = "Look at the new dropbox logo: https://www.dropbox.com/static/images/home_logo.png"
        with mock.patch("zerver.lib.markdown.fetch_open_graph_image", return_value=None):
            converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            '<p>Look at the new dropbox logo: <a href="https://www.dropbox.com/static/images/home_logo.png">https://www.dropbox.com/static/images/home_logo.png</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/static/images/home_logo.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fwww.dropbox.com%2Fstatic%2Fimages%2Fhome_logo.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fwww.dropbox.com%2Fstatic%2Fimages%2Fhome_logo.png&amp;size=thumbnail"></a></div>',
        )

    def test_inline_dropbox_bad(self) -> None:
        # Don't fail on bad dropbox links
        msg = "https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM"
        with mock.patch("zerver.lib.markdown.fetch_open_graph_image", return_value=None):
            converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            '<p><a href="https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM">https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM</a></p>',
        )

    @override_settings(THUMBNAIL_IMAGES=True)
    def test_inline_github_preview(self) -> None:
        # Test photo album previews
        msg = "Test: https://github.com/zulip/zulip/blob/main/static/images/logo/zulip-icon-128x128.png"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            '<p>Test: <a href="https://github.com/zulip/zulip/blob/main/static/images/logo/zulip-icon-128x128.png">https://github.com/zulip/zulip/blob/main/static/images/logo/zulip-icon-128x128.png</a></p>\n<div class="message_inline_image"><a href="https://github.com/zulip/zulip/blob/main/static/images/logo/zulip-icon-128x128.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fraw.githubusercontent.com%2Fzulip%2Fzulip%2Fmain%2Fstatic%2Fimages%2Flogo%2Fzulip-icon-128x128.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fraw.githubusercontent.com%2Fzulip%2Fzulip%2Fmain%2Fstatic%2Fimages%2Flogo%2Fzulip-icon-128x128.png&amp;size=thumbnail"></a></div>',
        )

        msg = "Test: https://developer.github.com/assets/images/hero-circuit-bg.png"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            '<p>Test: <a href="https://developer.github.com/assets/images/hero-circuit-bg.png">https://developer.github.com/assets/images/hero-circuit-bg.png</a></p>\n<div class="message_inline_image"><a href="https://developer.github.com/assets/images/hero-circuit-bg.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fdeveloper.github.com%2Fassets%2Fimages%2Fhero-circuit-bg.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fdeveloper.github.com%2Fassets%2Fimages%2Fhero-circuit-bg.png&amp;size=thumbnail"></a></div>',
        )

    def test_inline_youtube_preview(self) -> None:
        # Test YouTube URLs in spoilers
        msg = """\n```spoiler Check out this PyCon video\nhttps://www.youtube.com/watch?v=0c46YHS3RY8\n```"""
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<div class="spoiler-block"><div class="spoiler-header">\n<p>Check out this PyCon video</p>\n</div><div class="spoiler-content" aria-hidden="true">\n<p><a href="https://www.youtube.com/watch?v=0c46YHS3RY8">https://www.youtube.com/watch?v=0c46YHS3RY8</a></p>\n<div class="youtube-video message_inline_image"><a data-id="0c46YHS3RY8" href="https://www.youtube.com/watch?v=0c46YHS3RY8"><img src="{get_camo_url("https://i.ytimg.com/vi/0c46YHS3RY8/default.jpg")}"></a></div></div></div>""",
        )

        # Test YouTube URLs in normal messages.
        msg = "[YouTube link](https://www.youtube.com/watch?v=0c46YHS3RY8)"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="https://www.youtube.com/watch?v=0c46YHS3RY8">YouTube link</a></p>\n<div class="youtube-video message_inline_image"><a data-id="0c46YHS3RY8" href="https://www.youtube.com/watch?v=0c46YHS3RY8"><img src="{get_camo_url("https://i.ytimg.com/vi/0c46YHS3RY8/default.jpg")}"></a></div>""",
        )

        msg = "https://www.youtube.com/watch?v=0c46YHS3RY8\n\nSample text\n\nhttps://www.youtube.com/watch?v=lXFO2ULktEI"
        converted = markdown_convert_wrapper(msg)

        self.assertEqual(
            converted,
            f"""<p><a href="https://www.youtube.com/watch?v=0c46YHS3RY8">https://www.youtube.com/watch?v=0c46YHS3RY8</a></p>\n<div class="youtube-video message_inline_image"><a data-id="0c46YHS3RY8" href="https://www.youtube.com/watch?v=0c46YHS3RY8"><img src="{get_camo_url("https://i.ytimg.com/vi/0c46YHS3RY8/default.jpg")}"></a></div><p>Sample text</p>\n<p><a href="https://www.youtube.com/watch?v=lXFO2ULktEI">https://www.youtube.com/watch?v=lXFO2ULktEI</a></p>\n<div class="youtube-video message_inline_image"><a data-id="lXFO2ULktEI" href="https://www.youtube.com/watch?v=lXFO2ULktEI"><img src="{get_camo_url("https://i.ytimg.com/vi/lXFO2ULktEI/default.jpg")}"></a></div>""",
        )

        # Test order of YouTube inline previews in same paragraph.
        msg = "https://www.youtube.com/watch?v=0c46YHS3RY8\nhttps://www.youtube.com/watch?v=lXFO2ULktEI"
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            f"""<p><a href="https://www.youtube.com/watch?v=0c46YHS3RY8">https://www.youtube.com/watch?v=0c46YHS3RY8</a><br>\n<a href="https://www.youtube.com/watch?v=lXFO2ULktEI">https://www.youtube.com/watch?v=lXFO2ULktEI</a></p>\n<div class="youtube-video message_inline_image"><a data-id="0c46YHS3RY8" href="https://www.youtube.com/watch?v=0c46YHS3RY8"><img src="{get_camo_url("https://i.ytimg.com/vi/0c46YHS3RY8/default.jpg")}"></a></div><div class="youtube-video message_inline_image"><a data-id="lXFO2ULktEI" href="https://www.youtube.com/watch?v=lXFO2ULktEI"><img src="{get_camo_url("https://i.ytimg.com/vi/lXFO2ULktEI/default.jpg")}"></a></div>""",
        )

    def test_twitter_id_extraction(self) -> None:
        self.assertEqual(
            get_tweet_id("http://twitter.com/#!/VizzQuotes/status/409030735191097344"),
            "409030735191097344",
        )
        self.assertEqual(
            get_tweet_id("http://twitter.com/VizzQuotes/status/409030735191097344"),
            "409030735191097344",
        )
        self.assertEqual(
            get_tweet_id("http://twitter.com/VizzQuotes/statuses/409030735191097344"),
            "409030735191097344",
        )
        self.assertEqual(get_tweet_id("https://twitter.com/wdaher/status/1017581858"), "1017581858")
        self.assertEqual(
            get_tweet_id("https://twitter.com/wdaher/status/1017581858/"), "1017581858"
        )
        self.assertEqual(
            get_tweet_id("https://twitter.com/windyoona/status/410766290349879296/photo/1"),
            "410766290349879296",
        )
        self.assertEqual(
            get_tweet_id("https://twitter.com/windyoona/status/410766290349879296/"),
            "410766290349879296",
        )

    def test_fetch_tweet_data_settings_validation(self) -> None:
        with self.settings(TEST_SUITE=False, TWITTER_CONSUMER_KEY=None):
            with self.assertRaises(NotImplementedError):
                fetch_tweet_data("287977969287315459")

    def test_content_has_emoji(self) -> None:
        self.assertFalse(content_has_emoji_syntax("boring"))
        self.assertFalse(content_has_emoji_syntax("hello: world"))
        self.assertFalse(content_has_emoji_syntax(":foobar"))
        self.assertFalse(content_has_emoji_syntax("::: hello :::"))

        self.assertTrue(content_has_emoji_syntax("foo :whatever:"))
        self.assertTrue(content_has_emoji_syntax("\n:whatever:"))
        self.assertTrue(content_has_emoji_syntax(":smile: ::::::"))

    def test_realm_emoji(self) -> None:
        def emoji_img(name: str, file_name: str, realm_id: int) -> str:
            return '<img alt="{}" class="emoji" src="{}" title="{}">'.format(
                name, get_emoji_url(file_name, realm_id), name[1:-1].replace("_", " ")
            )

        realm = get_realm("zulip")

        # Needs to mock an actual message because that's how Markdown obtains the realm
        msg = Message(sender=self.example_user("hamlet"), realm=realm)
        converted = markdown_convert(":green_tick:", message_realm=realm, message=msg)
        realm_emoji = RealmEmoji.objects.filter(
            realm=realm, name="green_tick", deactivated=False
        ).get()
        assert realm_emoji.file_name is not None
        self.assertEqual(
            converted.rendered_content,
            "<p>{}</p>".format(emoji_img(":green_tick:", realm_emoji.file_name, realm.id)),
        )

        # Deactivate realm emoji.
        do_remove_realm_emoji(realm, "green_tick", acting_user=None)
        converted = markdown_convert(":green_tick:", message_realm=realm, message=msg)
        self.assertEqual(converted.rendered_content, "<p>:green_tick:</p>")

    def test_deactivated_realm_emoji(self) -> None:
        # Deactivate realm emoji.
        realm = get_realm("zulip")
        do_remove_realm_emoji(realm, "green_tick", acting_user=None)

        msg = Message(sender=self.example_user("hamlet"), realm=realm)
        converted = markdown_convert(":green_tick:", message_realm=realm, message=msg)
        self.assertEqual(converted.rendered_content, "<p>:green_tick:</p>")

    def test_unicode_emoji(self) -> None:
        msg = "\u2615"  # ☕
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            '<p><span aria-label="coffee" class="emoji emoji-2615" role="img" title="coffee">:coffee:</span></p>',
        )

        msg = "\u2615\u2615"  # ☕☕
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            '<p><span aria-label="coffee" class="emoji emoji-2615" role="img" title="coffee">:coffee:</span><span aria-label="coffee" class="emoji emoji-2615" role="img" title="coffee">:coffee:</span></p>',
        )

    def test_no_translate_emoticons_if_off(self) -> None:
        user_profile = self.example_user("othello")
        do_change_user_setting(user_profile, "translate_emoticons", False, acting_user=None)
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        content = ":)"
        expected = "<p>:)</p>"
        converted = render_message_markdown(msg, content)
        self.assertEqual(converted.rendered_content, expected)

    def test_same_markup(self) -> None:
        msg = "\u2615"  # ☕
        unicode_converted = markdown_convert_wrapper(msg)

        msg = ":coffee:"  # ☕☕
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(converted, unicode_converted)

    def test_links_in_topic_name(self) -> None:
        realm = get_realm("zulip")
        msg = Message(sender=self.example_user("othello"), realm=realm)

        msg.set_topic_name("https://google.com/hello-world")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [{"url": "https://google.com/hello-world", "text": "https://google.com/hello-world"}],
        )

        msg.set_topic_name("http://google.com/hello-world")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [{"url": "http://google.com/hello-world", "text": "http://google.com/hello-world"}],
        )

        msg.set_topic_name("Without scheme google.com/hello-world")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [{"url": "https://google.com/hello-world", "text": "google.com/hello-world"}],
        )

        msg.set_topic_name("Without scheme random.words/hello-world")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(converted_topic, [])

        msg.set_topic_name(
            "Try out http://ftp.debian.org, https://google.com/ and https://google.in/."
        )
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "http://ftp.debian.org", "text": "http://ftp.debian.org"},
                {"url": "https://google.com/", "text": "https://google.com/"},
                {"url": "https://google.in/", "text": "https://google.in/"},
            ],
        )

        # test order for links without scheme
        msg.set_topic_name("google.in google.com")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://google.in", "text": "google.in"},
                {"url": "https://google.com", "text": "google.com"},
            ],
        )

        # Query strings in a URL should be included in the link.
        msg.set_topic_name("https://google.com/test?foo=bar")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {
                    "url": "https://google.com/test?foo=bar",
                    "text": "https://google.com/test?foo=bar",
                },
            ],
        )
        # But question marks at the end of sentence are not part of the URL.
        msg.set_topic_name("Have you seen github.com/zulip?")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://github.com/zulip", "text": "github.com/zulip"},
            ],
        )
        msg.set_topic_name("Do you like https://example.com? I love it.")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://example.com", "text": "https://example.com"},
            ],
        )

    def check_add_linkifiers(
        self, linkifiers: List[RealmFilter], expected_linkifier_reprs: List[str]
    ) -> None:
        self.assert_length(linkifiers, len(expected_linkifier_reprs))
        for linkifier, expected_linkifier_repr in zip(linkifiers, expected_linkifier_reprs):
            linkifier.clean()
            linkifier.save()
            self.assertEqual(repr(linkifier), expected_linkifier_repr)

    def test_realm_patterns(self) -> None:
        realm = get_realm("zulip")
        self.check_add_linkifiers(
            [
                RealmFilter(
                    realm=realm,
                    pattern=r"#(?P<id>[0-9]{2,8})",
                    url_template=r"https://trac.example.com/ticket/{id}",
                )
            ],
            ["<RealmFilter: zulip: #(?P<id>[0-9]{2,8}) https://trac.example.com/ticket/{id}>"],
        )

        msg = Message(sender=self.example_user("othello"), realm=realm)
        msg.set_topic_name("#444")

        flush_per_request_caches()

        content = "We should fix #224 #336 #446 and #115, but not issue#124 or #1124z or [trac #15](https://trac.example.com/ticket/16) today."
        converted = markdown_convert(content, message_realm=realm, message=msg)
        converted_topic = topic_links(realm.id, msg.topic_name())

        self.assertEqual(
            converted.rendered_content,
            '<p>We should fix <a href="https://trac.example.com/ticket/224">#224</a> <a href="https://trac.example.com/ticket/336">#336</a> <a href="https://trac.example.com/ticket/446">#446</a> and <a href="https://trac.example.com/ticket/115">#115</a>, but not issue#124 or #1124z or <a href="https://trac.example.com/ticket/16">trac #15</a> today.</p>',
        )
        self.assertEqual(
            converted_topic, [{"url": "https://trac.example.com/ticket/444", "text": "#444"}]
        )

        msg.set_topic_name("#444 https://google.com")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://trac.example.com/ticket/444", "text": "#444"},
                {"url": "https://google.com", "text": "https://google.com"},
            ],
        )

        msg.set_topic_name("#111 https://google.com #111 #222 #111 https://google.com #222")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://trac.example.com/ticket/111", "text": "#111"},
                {"url": "https://google.com", "text": "https://google.com"},
                {"url": "https://trac.example.com/ticket/111", "text": "#111"},
                {"url": "https://trac.example.com/ticket/222", "text": "#222"},
                {"url": "https://trac.example.com/ticket/111", "text": "#111"},
                {"url": "https://google.com", "text": "https://google.com"},
                {"url": "https://trac.example.com/ticket/222", "text": "#222"},
            ],
        )

        msg.set_topic_name("#444 #555 #666")
        converted_topic = topic_links(realm.id, msg.topic_name())
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://trac.example.com/ticket/444", "text": "#444"},
                {"url": "https://trac.example.com/ticket/555", "text": "#555"},
                {"url": "https://trac.example.com/ticket/666", "text": "#666"},
            ],
        )

        RealmFilter(
            realm=realm,
            pattern=r"#(?P<id>[a-zA-Z]+-[0-9]+)",
            url_template=r"https://trac.example.com/ticket/{id}",
        ).save()
        msg = Message(sender=self.example_user("hamlet"), realm=realm)

        content = "#ZUL-123 was fixed and code was deployed to production, also #zul-321 was deployed to staging"
        converted = markdown_convert(content, message_realm=realm, message=msg)

        self.assertEqual(
            converted.rendered_content,
            '<p><a href="https://trac.example.com/ticket/ZUL-123">#ZUL-123</a> was fixed and code was deployed to production, also <a href="https://trac.example.com/ticket/zul-321">#zul-321</a> was deployed to staging</p>',
        )

        def assert_conversion(content: str, should_have_converted: bool = True) -> None:
            converted = markdown_convert(content, message_realm=realm, message=msg).rendered_content
            converted_topic = topic_links(realm.id, content)
            if should_have_converted:
                self.assertTrue("https://trac.example.com" in converted)
                self.assert_length(converted_topic, 1)
                self.assertEqual(
                    converted_topic[0],
                    {"url": "https://trac.example.com/ticket/123", "text": "#123"},
                )
            else:
                self.assertTrue("https://trac.example.com" not in converted)
                self.assert_length(converted_topic, 0)

        assert_conversion("Hello #123 World")
        assert_conversion("Hello #123World", False)
        assert_conversion("Hello#123 World", False)
        assert_conversion("Hello#123World", False)
        assert_conversion("Hello\u00a0#123\u00a0World")
        # Ideally, these should be converted, but Markdown doesn't
        # handle word boundary detection in languages that don't use
        # whitespace for that correctly yet.
        assert_conversion("チケットは#123です", False)
        assert_conversion("チケットは #123です", False)
        assert_conversion("チケットは#123 です", False)
        assert_conversion("チケットは #123 です")
        assert_conversion("(#123)")
        assert_conversion("#123>")
        assert_conversion('"#123"')
        assert_conversion("#123@")
        assert_conversion(")#123(", False)
        assert_conversion("##123", False)

        # test nested realm patterns should avoid double matching
        RealmFilter(
            realm=realm,
            pattern=r"hello#(?P<id>[0-9]+)",
            url_template=r"https://trac.example.com/hello/{id}",
        ).save()
        converted_topic = topic_links(realm.id, "hello#123 #234")
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://trac.example.com/hello/123", "text": "hello#123"},
                {"url": "https://trac.example.com/ticket/234", "text": "#234"},
            ],
        )

        # test correct order when realm pattern and normal links are both present.
        converted_topic = topic_links(realm.id, "#234 https://google.com")
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://trac.example.com/ticket/234", "text": "#234"},
                {"url": "https://google.com", "text": "https://google.com"},
            ],
        )

        # Test URL escaping
        RealmFilter(
            realm=realm,
            pattern=r"url-(?P<id>[0-9]+)",
            url_template="https://example.com/A%20Test/%%%ba/{id}",
        ).save()
        msg = Message(sender=self.example_user("hamlet"), realm=realm)
        content = "url-123 is well-escaped"
        converted = markdown_convert(content, message_realm=realm, message=msg)
        self.assertEqual(
            converted.rendered_content,
            '<p><a href="https://example.com/A%20Test/%25%25%ba/123">url-123</a> is well-escaped</p>',
        )
        converted_topic = topic_links(realm.id, content)
        self.assertEqual(
            converted_topic,
            [{"url": "https://example.com/A%20Test/%25%25%ba/123", "text": "url-123"}],
        )

        # Test spaces in the linkifier pattern
        RealmFilter(
            realm=realm,
            pattern=r"community guidelines",
            url_template="https://zulip.com/development-community/#community-norms",
        ).save()
        converted = markdown_convert("community guidelines", message_realm=realm, message=msg)
        self.assertEqual(
            converted.rendered_content,
            '<p><a href="https://zulip.com/development-community/#community-norms">community guidelines</a></p>',
        )
        converted = markdown_convert(
            "please observe community guidelines here", message_realm=realm, message=msg
        )
        self.assertEqual(
            converted.rendered_content,
            '<p>please observe <a href="https://zulip.com/development-community/#community-norms">community guidelines</a> here</p>',
        )

    def test_multiple_matching_realm_patterns(self) -> None:
        realm = get_realm("zulip")
        self.check_add_linkifiers(
            [
                RealmFilter(
                    realm=realm,
                    pattern="(?P<id>ABC-[0-9]+)",
                    url_template="https://trac.example.com/ticket/{id}",
                ),
                RealmFilter(
                    realm=realm,
                    pattern="(?P<id>[A-Z][A-Z0-9]*-[0-9]+)",
                    url_template="https://other-trac.example.com/ticket/{id}",
                ),
                RealmFilter(
                    realm=realm,
                    pattern="(?P<id>[A-Z][A-Z0-9]+)",
                    url_template="https://yet-another-trac.example.com/ticket/{id}",
                ),
            ],
            [
                "<RealmFilter: zulip: (?P<id>ABC-[0-9]+) https://trac.example.com/ticket/{id}>",
                "<RealmFilter: zulip: (?P<id>[A-Z][A-Z0-9]*-[0-9]+) https://other-trac.example.com/ticket/{id}>",
                "<RealmFilter: zulip: (?P<id>[A-Z][A-Z0-9]+) https://yet-another-trac.example.com/ticket/{id}>",
            ],
        )

        msg = Message(sender=self.example_user("othello"), realm=realm)
        msg.set_topic_name("ABC-123")

        flush_per_request_caches()

        content = (
            "We should fix ABC-123 or [trac ABC-123](https://trac.example.com/ticket/16) today."
        )
        converted = markdown_convert(content, message_realm=realm, message=msg)
        converted_topic = topic_links(realm.id, msg.topic_name())

        # The second linkifier (which was saved later) was ignored as the content was marked AtomicString after first conversion.
        # There was no easy way to support parsing both linkifiers and not run into an infinite loop, hence the second linkifier is ignored.
        self.assertEqual(
            converted.rendered_content,
            '<p>We should fix <a href="https://trac.example.com/ticket/ABC-123">ABC-123</a> or <a href="https://trac.example.com/ticket/16">trac ABC-123</a> today.</p>',
        )
        # Only the older linkifier should be used in the topic, because the two patterns overlap.
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://trac.example.com/ticket/ABC-123", "text": "ABC-123"},
            ],
        )

        # linkifier 3 matches ASD, ABC and QWE, but because it has lower priority
        # than linkifier 1 and linkifier 2 because it is created last, the former
        # two matches will not be chosen.
        # Both linkifier 1 and linkifier 2 matches ABC-123, similarly, as linkifier 2
        # has a lower priority, only linkifier 1's URL will be generated.
        converted_topic = topic_links(realm.id, "ASD-123 ABC-123 QWE")
        self.assertEqual(
            converted_topic,
            [
                {"url": "https://other-trac.example.com/ticket/ASD-123", "text": "ASD-123"},
                {"url": "https://trac.example.com/ticket/ABC-123", "text": "ABC-123"},
                {"url": "https://yet-another-trac.example.com/ticket/QWE", "text": "QWE"},
            ],
        )

    def test_links_and_linkifiers_in_topic_name(self) -> None:
        realm = get_realm("zulip")
        self.check_add_linkifiers(
            [
                RealmFilter(
                    realm=realm,
                    pattern="ABC-42",
                    url_template="https://google.com",
                ),
                RealmFilter(
                    realm=realm,
                    pattern=r"com.+(?P<id>ABC\-[0-9]+)",
                    url_template="https://trac.example.com/ticket/{id}",
                ),
            ],
            [
                "<RealmFilter: zulip: ABC-42 https://google.com>",
                r"<RealmFilter: zulip: com.+(?P<id>ABC\-[0-9]+) https://trac.example.com/ticket/{id}>",
            ],
        )

        # This verifies that second linkifier has a lower priority than the first one.
        # It helps us to later ensure that even with a low priority, the linkifier can take effect
        # when it appears earlier than a raw URL.
        converted_topic = topic_links(realm.id, "com ABC-42")
        self.assertEqual(
            converted_topic,
            [{"url": "https://google.com", "text": "ABC-42"}],
        )
        # The linkifier matches "com/ABC-123", which is after where the raw URL starts
        converted_topic = topic_links(realm.id, "https://foo.com/ABC-123")
        self.assertEqual(
            converted_topic,
            [{"url": "https://foo.com/ABC-123", "text": "https://foo.com/ABC-123"}],
        )

        # The linkifier matches "com https://foo.com/ABC-123", which is before where the raw URL starts
        converted_topic = topic_links(realm.id, "com https://foo.com/ABC-123")
        self.assertEqual(
            converted_topic,
            [
                {
                    "url": "https://trac.example.com/ticket/ABC-123",
                    "text": "com https://foo.com/ABC-123",
                }
            ],
        )

    def test_topic_links_ordering_by_priority(self) -> None:
        # The same test case is also implemented in web/tests/markdown_parse.test.js
        realm = get_realm("zulip")
        self.check_add_linkifiers(
            [
                RealmFilter(
                    realm=realm,
                    pattern="http",
                    url_template="http://example.com/",
                    order=1,
                ),
                RealmFilter(
                    realm=realm,
                    pattern="b#(?P<id>[a-z]+)",
                    url_template="http://example.com/b/{id}",
                    order=2,
                ),
                RealmFilter(
                    realm=realm,
                    pattern="a#(?P<aid>[a-z]+) b#(?P<bid>[a-z]+)",
                    url_template="http://example.com/a/{aid}/b/{bid}",
                    order=3,
                ),
                RealmFilter(
                    realm=realm,
                    pattern="a#(?P<id>[a-z]+)",
                    url_template="http://example.com/a/{id}",
                    order=4,
                ),
            ],
            [
                "<RealmFilter: zulip: http http://example.com/>",
                "<RealmFilter: zulip: b#(?P<id>[a-z]+) http://example.com/b/{id}>",
                "<RealmFilter: zulip: a#(?P<aid>[a-z]+) b#(?P<bid>[a-z]+) http://example.com/a/{aid}/b/{bid}>",
                "<RealmFilter: zulip: a#(?P<id>[a-z]+) http://example.com/a/{id}>",
            ],
        )
        # There should be 5 link matches in the topic, if ordered from the most prioritized to the least:
        # 1. "http" (linkifier)
        # 2. "b#bar" (linkifier)
        # 3. "a#asd b#bar" (linkifier)
        # 4. "a#asd" (linkifier)
        # 5. "http://foo.com" (raw URL)
        # When there are overlapping matches, the one that appears earlier in the list should
        # have a topic link generated.
        # For this test case, while "a#asd" and "a#asd b#bar" both match and they overlap,
        # there is a match "b#bar" with a higher priority, preventing "a#asd b#bar" from being matched.
        converted_topic = topic_links(realm.id, "http://foo.com a#asd b#bar")
        self.assertEqual(
            converted_topic,
            [
                {
                    "text": "http",
                    "url": "http://example.com/",
                },
                {
                    "text": "a#asd",
                    "url": "http://example.com/a/asd",
                },
                {
                    "text": "b#bar",
                    "url": "http://example.com/b/bar",
                },
            ],
        )

    def test_linkifier_precedence(self) -> None:
        realm = self.example_user("hamlet").realm
        RealmFilter.objects.filter(realm=realm).delete()
        # The insertion order should not affect the fact that the linkifiers are
        # ordered by the `order` field.
        order_values = (10, 3, 11, 2, 4, 5, 6)
        order_to_id = {}
        for cur_order in order_values:
            linkifier = RealmFilter(
                realm=realm,
                pattern=f"abc{cur_order}",
                url_template="http://foo.com",
                order=cur_order,
            )
            linkifier.save()
            order_to_id[cur_order] = linkifier.id
        linkifiers = linkifiers_for_realm(realm.id)
        for index, cur_order in enumerate(sorted(order_values)):
            self.assertEqual(linkifiers[index]["id"], order_to_id[cur_order])

    def test_realm_patterns_negative(self) -> None:
        realm = get_realm("zulip")
        RealmFilter(
            realm=realm,
            pattern=r"#(?P<id>[0-9]{2,8})",
            url_template=r"https://trac.example.com/ticket/{id}",
        ).save()
        boring_msg = Message(sender=self.example_user("othello"), realm=realm)
        boring_msg.set_topic_name("no match here")
        converted_boring_topic = topic_links(realm.id, boring_msg.topic_name())
        self.assertEqual(converted_boring_topic, [])

    def test_is_status_message(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        content = "/me makes a list\n* one\n* two"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>/me makes a list</p>\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>",
        )
        self.assertTrue(Message.is_status_message(content, rendering_result.rendered_content))

        content = "/me takes a walk"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>/me takes a walk</p>",
        )
        self.assertTrue(Message.is_status_message(content, rendering_result.rendered_content))

        content = "/me writes a second line\nline"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>/me writes a second line<br>\nline</p>",
        )
        self.assertTrue(Message.is_status_message(content, rendering_result.rendered_content))

    def test_linkifier_caching(self) -> None:
        realm = get_realm("zulip")

        RealmFilter.objects.all().delete()

        with self.assert_database_query_count(1):
            self.assertEqual(linkifiers_for_realm(realm.id), [])

        # Verify that our in-memory cache avoids round trips.
        with self.assert_database_query_count(0, keep_cache_warm=True):
            with self.assert_memcached_count(0):
                self.assertEqual(linkifiers_for_realm(realm.id), [])

        linkifier = RealmFilter(realm=realm, pattern=r"whatever", url_template="whatever")
        linkifier.save()

        # cache gets properly invalidated by virtue of our save
        self.assertEqual(
            linkifiers_for_realm(realm.id),
            [{"id": linkifier.id, "pattern": "whatever", "url_template": "whatever"}],
        )

        # And the in-process cache works again.
        with self.assert_database_query_count(0, keep_cache_warm=True):
            with self.assert_memcached_count(0):
                self.assertEqual(
                    linkifiers_for_realm(realm.id),
                    [{"id": linkifier.id, "pattern": "whatever", "url_template": "whatever"}],
                )

    def test_alert_words(self) -> None:
        user_profile = self.example_user("othello")
        do_add_alert_words(user_profile, ["ALERTWORD", "scaryword"])
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )
        realm_alert_words_automaton = get_alert_word_automaton(user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = "We have an ALERTWORD day today!"
        rendering_result = render(msg, content)
        self.assertEqual(
            rendering_result.rendered_content, "<p>We have an ALERTWORD day today!</p>"
        )
        self.assertEqual(rendering_result.user_ids_with_alert_words, {user_profile.id})

        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )
        content = "We have a NOTHINGWORD day today!"
        rendering_result = render(msg, content)
        self.assertEqual(
            rendering_result.rendered_content, "<p>We have a NOTHINGWORD day today!</p>"
        )
        self.assertEqual(rendering_result.user_ids_with_alert_words, set())

    def test_alert_words_returns_user_ids_with_alert_words(self) -> None:
        alert_words_for_users: Dict[str, List[str]] = {
            "hamlet": ["how"],
            "cordelia": ["this possible"],
            "iago": ["hello"],
            "prospero": ["hello"],
            "othello": ["how are you"],
            "aaron": ["hey"],
        }
        user_profiles: Dict[str, UserProfile] = {}
        for username, alert_words in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_add_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user("polonius")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = "hello how is this possible how are you doing today"
        rendering_result = render(msg, content)
        expected_user_ids: Set[int] = {
            user_profiles["hamlet"].id,
            user_profiles["cordelia"].id,
            user_profiles["iago"].id,
            user_profiles["prospero"].id,
            user_profiles["othello"].id,
        }
        # All users except aaron have their alert word appear in the message content
        self.assertEqual(rendering_result.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_user_ids_with_alert_words_1(self) -> None:
        alert_words_for_users: Dict[str, List[str]] = {
            "hamlet": ["provisioning", "Prod deployment"],
            "cordelia": ["test", "Prod"],
            "iago": ["prod"],
            "prospero": ["deployment"],
            "othello": ["last"],
        }
        user_profiles: Dict[str, UserProfile] = {}
        for username, alert_words in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_add_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user("polonius")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = """Hello, everyone. Prod deployment has been completed
        And this is a new line
        to test out how Markdown convert this into something line ending split array
        and this is a new line
        last"""
        rendering_result = render(msg, content)
        expected_user_ids: Set[int] = {
            user_profiles["hamlet"].id,
            user_profiles["cordelia"].id,
            user_profiles["iago"].id,
            user_profiles["prospero"].id,
            user_profiles["othello"].id,
        }
        # All users have their alert word appear in the message content
        self.assertEqual(rendering_result.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_user_ids_with_alert_words_in_french(self) -> None:
        alert_words_for_users: Dict[str, List[str]] = {
            "hamlet": ["réglementaire", "une politique", "une merveille"],
            "cordelia": ["énormément", "Prod"],
            "iago": ["prod"],
            "prospero": ["deployment"],
            "othello": ["last"],
        }
        user_profiles: Dict[str, UserProfile] = {}
        for username, alert_words in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_add_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user("polonius")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = """This is to test out alert words work in languages with accented characters too
        bonjour est (énormément) ce a quoi ressemble le français
        et j'espère qu'il n'y n' réglementaire a pas de mots d'alerte dans ce texte français
        """
        rendering_result = render(msg, content)
        expected_user_ids: Set[int] = {user_profiles["hamlet"].id, user_profiles["cordelia"].id}
        # Only hamlet and cordelia have their alert-words appear in the message content
        self.assertEqual(rendering_result.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_empty_user_ids_with_alert_words(self) -> None:
        alert_words_for_users: Dict[str, List[str]] = {
            "hamlet": [],
            "cordelia": [],
            "iago": [],
            "prospero": [],
            "othello": [],
            "aaron": [],
        }
        user_profiles: Dict[str, UserProfile] = {}
        for username, alert_words in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_add_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user("polonius")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = """hello how is this possible how are you doing today
        This is to test that the no user_ids who have alrert wourldword is participating
        in sending of the message
        """
        rendering_result = render(msg, content)
        expected_user_ids: Set[int] = set()
        # None of the users have their alert-words appear in the message content
        self.assertEqual(rendering_result.user_ids_with_alert_words, expected_user_ids)

    def get_mock_alert_words(self, num_words: int, word_length: int) -> List[str]:
        alert_words = ["x" * word_length] * num_words  # type List[str]
        return alert_words

    def test_alert_words_with_empty_alert_words(self) -> None:
        alert_words_for_users: Dict[str, List[str]] = {
            "hamlet": [],
            "cordelia": [],
            "iago": [],
            "othello": [],
        }
        user_profiles: Dict[str, UserProfile] = {}
        for username, alert_words in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_add_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user("polonius")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = """This is to test a empty alert words i.e. no user has any alert-words set"""
        rendering_result = render(msg, content)
        expected_user_ids: Set[int] = set()
        self.assertEqual(rendering_result.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_user_ids_with_alert_words_with_huge_alert_words(self) -> None:
        alert_words_for_users: Dict[str, List[str]] = {
            "hamlet": ["issue124"],
            "cordelia": self.get_mock_alert_words(500, 10),
            "iago": self.get_mock_alert_words(500, 10),
            "othello": self.get_mock_alert_words(500, 10),
        }
        user_profiles: Dict[str, UserProfile] = {}
        for username, alert_words in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_add_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user("polonius")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> MessageRenderingResult:
            return render_message_markdown(
                msg, content, realm_alert_words_automaton=realm_alert_words_automaton
            )

        content = """The code above will print 10 random values of numbers between 1 and 100.
        The second line, for x in range(10), determines how many values will be printed (when you use
        range(x), the number that you use in place of x will be the amount of values that you'll have
        printed. if you want 20 values, use range(20). use range(5) if you only want 5 values returned,
        etc.). I was talking about the issue124 on github. Then the third line: print random.randint(1,101) will automatically select a random integer
        between 1 and 100 for you. The process is fairly simple
        """
        rendering_result = render(msg, content)
        expected_user_ids: Set[int] = {user_profiles["hamlet"].id}
        # Only hamlet has alert-word 'issue124' present in the message content
        self.assertEqual(rendering_result.user_ids_with_alert_words, expected_user_ids)

    def test_default_code_block_language(self) -> None:
        realm = get_realm("zulip")
        self.assertEqual(realm.default_code_block_language, "")
        text = "```{}\nconsole.log('Hello World');\n```\n"

        # Render without default language
        msg_with_js = markdown_convert_wrapper(text.format("js"))
        msg_with_python = markdown_convert_wrapper(text.format("python"))
        msg_without_language = markdown_convert_wrapper(text.format(""))
        msg_with_quote = markdown_convert_wrapper(text.format("quote"))
        msg_with_math = markdown_convert_wrapper(text.format("math"))
        msg_with_none = markdown_convert_wrapper(text.format("none"))

        # Render with default=javascript
        do_set_realm_property(realm, "default_code_block_language", "javascript", acting_user=None)
        msg_without_language_default_js = markdown_convert_wrapper(text.format(""))
        msg_with_python_default_js = markdown_convert_wrapper(text.format("python"))

        # Render with default=python
        do_set_realm_property(realm, "default_code_block_language", "python", acting_user=None)
        msg_without_language_default_py = markdown_convert_wrapper(text.format(""))
        msg_with_none_default_py = markdown_convert_wrapper(text.format("none"))

        # Render with default=quote
        do_set_realm_property(realm, "default_code_block_language", "quote", acting_user=None)
        msg_without_language_default_quote = markdown_convert_wrapper(text.format(""))

        # Render with default=math
        do_set_realm_property(realm, "default_code_block_language", "math", acting_user=None)
        msg_without_language_default_math = markdown_convert_wrapper(text.format(""))

        # Render without default language
        do_set_realm_property(realm, "default_code_block_language", "", acting_user=None)
        msg_without_language_final = markdown_convert_wrapper(text.format(""))

        self.assertTrue(msg_with_js == msg_without_language_default_js)
        self.assertTrue(
            msg_with_python == msg_with_python_default_js == msg_without_language_default_py
        )
        self.assertTrue(msg_with_quote == msg_without_language_default_quote)
        self.assertTrue(msg_with_math == msg_without_language_default_math)
        self.assertTrue(msg_without_language == msg_without_language_final)
        self.assertTrue(msg_with_none == msg_with_none_default_py)

        # Test checking inside nested quotes
        nested_text = "````quote\n\n{}\n\n{}````".format(text.format("js"), text.format(""))
        do_set_realm_property(realm, "default_code_block_language", "javascript", acting_user=None)
        rendered = markdown_convert_wrapper(nested_text)
        with_language, without_language = re.findall(r"<pre>(.*?)$", rendered, re.MULTILINE)
        self.assertTrue(with_language == without_language)

        do_set_realm_property(realm, "default_code_block_language", "", acting_user=None)
        rendered = markdown_convert_wrapper(nested_text)
        with_language, without_language = re.findall(r"<pre>(.*?)$", rendered, re.MULTILINE)
        self.assertFalse(with_language == without_language)

    def test_mention_topic_wildcard(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        for topic_wildcard in topic_wildcards:
            content = f"@**{topic_wildcard}** test"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(
                rendering_result.rendered_content,
                f'<p><span class="topic-mention">@{topic_wildcard}</span> test</p>',
            )
            self.assertTrue(rendering_result.mentions_topic_wildcard)
            self.assertFalse(rendering_result.mentions_stream_wildcard)

    def test_mention_stream_wildcard(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        for stream_wildcard in stream_wildcards:
            content = f"@**{stream_wildcard}** test"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(
                rendering_result.rendered_content,
                f'<p><span class="user-mention" data-user-id="*">@{stream_wildcard}</span> test</p>',
            )
            self.assertFalse(rendering_result.mentions_topic_wildcard)
            self.assertTrue(rendering_result.mentions_stream_wildcard)

    def test_mention_at_topic_wildcard(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        for topic_wildcard in topic_wildcards:
            content = f"@{topic_wildcard} test"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(rendering_result.rendered_content, f"<p>@{topic_wildcard} test</p>")
            self.assertFalse(rendering_result.mentions_topic_wildcard)
            self.assertFalse(rendering_result.mentions_stream_wildcard)
            self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_at_stream_wildcard(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        for stream_wildcard in stream_wildcards:
            content = f"@{stream_wildcard} test"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(rendering_result.rendered_content, f"<p>@{stream_wildcard} test</p>")
            self.assertFalse(rendering_result.mentions_topic_wildcard)
            self.assertFalse(rendering_result.mentions_stream_wildcard)
            self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_word_starting_with_at_wildcard(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        content = "test @alleycat.com test"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.rendered_content, "<p>test @alleycat.com test</p>")
        self.assertFalse(rendering_result.mentions_stream_wildcard)
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_at_normal_user(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        content = "@aaron test"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.rendered_content, "<p>@aaron test</p>")
        self.assertFalse(rendering_result.mentions_stream_wildcard)
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_single(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )
        user_id = user_profile.id

        content = "@**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            f'<p><span class="user-mention" data-user-id="{user_id}">@King Hamlet</span></p>',
        )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})

        content = f"@**|{user_id}**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            f'<p><span class="user-mention" data-user-id="{user_id}">@King Hamlet</span></p>',
        )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})

    def test_mention_with_valid_special_characters_before(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id

        valid_characters_before_mention = ["(", "{", "[", "/", "<"]
        for character in valid_characters_before_mention:
            content = f"{character}@**King Hamlet**"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(
                rendering_result.rendered_content,
                f'<p>{escape(character)}<span class="user-mention" '
                f'data-user-id="{user_id}">'
                "@King Hamlet</span></p>",
            )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})

    def test_mention_with_invalid_special_characters_before(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )

        invalid_characters_before_mention = [".", ",", ";", ":", "#"]
        for character in invalid_characters_before_mention:
            content = f"{character}@**King Hamlet**"
            rendering_result = render_message_markdown(msg, content)
            unicode_character = escape(character)
            self.assertEqual(
                rendering_result.rendered_content,
                f"<p>{unicode_character}@<strong>King Hamlet</strong></p>",
            )

    def test_mention_silent(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id

        content = "@_**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention silent" '
            f'data-user-id="{user_id}">'
            "King Hamlet</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_deactivated_users(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        change_user_is_active(user_profile, False)
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id

        content = "@**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention silent" '
            f'data-user-id="{user_id}">'
            "King Hamlet</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_silent_deactivated_users(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        change_user_is_active(user_profile, False)
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id

        content = "@_**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention silent" '
            f'data-user-id="{user_id}">'
            "King Hamlet</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_mention_inaccessible_users(self) -> None:
        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")
        hamlet = self.example_user("hamlet")
        msg = Message(
            sender=polonius,
            sending_client=get_client("test"),
            realm=polonius.realm,
        )
        content = "@**Othello, the Moor of Venice** @**King Hamlet** test message"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p>@<strong>Othello, the Moor of Venice</strong> <span class="user-mention" '
            f'data-user-id="{hamlet.id}">'
            "@King Hamlet</span> test message</p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {hamlet.id})

        content = "@_**Othello, the Moor of Venice** @_**King Hamlet** test message"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p>@_<strong>Othello, the Moor of Venice</strong> <span class="user-mention silent" '
            f'data-user-id="{hamlet.id}">'
            "King Hamlet</span> test message</p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_silent_stream_wildcard_mention(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        for wildcard in stream_wildcards:
            content = f"@_**{wildcard}**"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(
                rendering_result.rendered_content,
                f'<p><span class="user-mention silent" data-user-id="*">{wildcard}</span></p>',
            )
            self.assertFalse(rendering_result.mentions_stream_wildcard)

    def test_silent_topic_wildcard_mention(self) -> None:
        user_profile = self.example_user("othello")
        msg = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        for wildcard in topic_wildcards:
            content = f"@_**{wildcard}**"
            rendering_result = render_message_markdown(msg, content)
            self.assertEqual(
                rendering_result.rendered_content,
                f'<p><span class="topic-mention silent">{wildcard}</span></p>',
            )
            self.assertFalse(rendering_result.mentions_topic_wildcard)

    def test_mention_invalid_followed_by_valid(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id

        content = "@**Invalid user** and @**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p>@<strong>Invalid user</strong> and <span class="user-mention" '
            f'data-user-id="{user_id}">'
            "@King Hamlet</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})

    def test_invalid_mention_not_uses_valid_mention_data(self) -> None:
        sender_user_profile = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )

        # Even though King Hamlet will be present in mention data as
        # it was fetched for first mention but second mention is
        # incorrect(as it uses hamlet's id) so it should not be able
        # to use that data for creating a valid mention.

        content = f"@**King Hamlet|{hamlet.id}** and @**aaron|{hamlet.id}**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            f'<p><span class="user-mention" data-user-id="{hamlet.id}">'
            f"@King Hamlet</span> and @<strong>aaron|{hamlet.id}</strong></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {hamlet.id})

    def test_silent_mention_invalid_followed_by_valid(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id

        content = "@_**Invalid user** and @_**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p>@_<strong>Invalid user</strong> and <span class="user-mention silent" '
            f'data-user-id="{user_id}">'
            "King Hamlet</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

        content = f"@_**|123456789** and @_**|{user_id}**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>@_<strong>|123456789</strong> and "
            '<span class="user-mention silent" '
            f'data-user-id="{user_id}">'
            "King Hamlet</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_possible_mentions(self) -> None:
        def assert_mentions(
            content: str,
            names: Set[str],
            has_topic_wildcards: bool = False,
            has_stream_wildcards: bool = False,
        ) -> None:
            self.assertEqual(
                possible_mentions(content),
                PossibleMentions(
                    mention_texts=names,
                    message_has_topic_wildcards=has_topic_wildcards,
                    message_has_stream_wildcards=has_stream_wildcards,
                ),
            )

        aaron = self.example_user("aaron")

        assert_mentions("", set())
        assert_mentions("boring", set())
        assert_mentions("@**topic**", set(), True)
        assert_mentions("@**all**", set(), False, True)
        assert_mentions("smush@**steve**smush", set())

        assert_mentions(
            f"Hello @**King Hamlet**, @**|{aaron.id}** and @**Cordelia, Lear's daughter**\n@**Foo van Barson|1234** @**all**",
            {"King Hamlet", f"|{aaron.id}", "Cordelia, Lear's daughter", "Foo van Barson|1234"},
            False,
            True,
        )

    def test_mention_multiple(self) -> None:
        sender_user_profile = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )

        content = "@**King Hamlet** and @**Cordelia, Lear's daughter**, check this out"

        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>"
            '<span class="user-mention" '
            f'data-user-id="{hamlet.id}">@King Hamlet</span> and '
            '<span class="user-mention" '
            f'data-user-id="{cordelia.id}">@Cordelia, Lear\'s daughter</span>, '
            "check this out</p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {hamlet.id, cordelia.id})

    def test_mention_in_quotes(self) -> None:
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        msg = Message(sender=othello, sending_client=get_client("test"), realm=othello.realm)

        content = "> @**King Hamlet** and @**Othello, the Moor of Venice**\n\n @**King Hamlet** and @**Cordelia, Lear's daughter**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<blockquote>\n<p>"
            f'<span class="user-mention silent" data-user-id="{hamlet.id}">King Hamlet</span>'
            " and "
            f'<span class="user-mention silent" data-user-id="{othello.id}">Othello, the Moor of Venice</span>'
            "</p>\n</blockquote>\n"
            "<p>"
            f'<span class="user-mention" data-user-id="{hamlet.id}">@King Hamlet</span>'
            " and "
            f'<span class="user-mention" data-user-id="{cordelia.id}">@Cordelia, Lear\'s daughter</span>'
            "</p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {hamlet.id, cordelia.id})

        # Both fenced quote and > quote should be identical for both silent and regular syntax.
        expected = (
            "<blockquote>\n<p>"
            f'<span class="user-mention silent" data-user-id="{hamlet.id}">King Hamlet</span>'
            "</p>\n</blockquote>"
        )
        content = "```quote\n@**King Hamlet**\n```"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.rendered_content, expected)
        self.assertEqual(rendering_result.mentions_user_ids, set())
        content = "> @**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.rendered_content, expected)
        self.assertEqual(rendering_result.mentions_user_ids, set())
        content = "```quote\n@_**King Hamlet**\n```"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.rendered_content, expected)
        self.assertEqual(rendering_result.mentions_user_ids, set())
        content = "> @_**King Hamlet**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.rendered_content, expected)
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_stream_wildcard_mention_in_quotes(self) -> None:
        user_profile = self.example_user("othello")
        message = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        def assert_silent_mention(content: str, wildcard: str) -> None:
            expected = (
                "<blockquote>\n<p>"
                f'<span class="user-mention silent" data-user-id="*">{wildcard}</span>'
                "</p>\n</blockquote>"
            )
            rendering_result = render_message_markdown(message, content)
            self.assertEqual(rendering_result.rendered_content, expected)
            self.assertFalse(rendering_result.mentions_stream_wildcard)
            self.assertFalse(rendering_result.mentions_topic_wildcard)

        for wildcard in stream_wildcards:
            assert_silent_mention(f"> @**{wildcard}**", wildcard)
            assert_silent_mention(f"> @_**{wildcard}**", wildcard)
            assert_silent_mention(f"```quote\n@**{wildcard}**\n```", wildcard)
            assert_silent_mention(f"```quote\n@_**{wildcard}**\n```", wildcard)

    def test_topic_wildcard_mention_in_quotes(self) -> None:
        user_profile = self.example_user("othello")
        message = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )

        def assert_silent_mention(content: str, wildcard: str) -> None:
            expected = (
                "<blockquote>\n<p>"
                f'<span class="topic-mention silent">{wildcard}</span>'
                "</p>\n</blockquote>"
            )
            rendering_result = render_message_markdown(message, content)
            self.assertEqual(rendering_result.rendered_content, expected)
            self.assertFalse(rendering_result.mentions_stream_wildcard)
            self.assertFalse(rendering_result.mentions_topic_wildcard)

        for wildcard in topic_wildcards:
            assert_silent_mention(f"> @**{wildcard}**", wildcard)
            assert_silent_mention(f"> @_**{wildcard}**", wildcard)
            assert_silent_mention(f"```quote\n@**{wildcard}**\n```", wildcard)
            assert_silent_mention(f"```quote\n@_**{wildcard}**\n```", wildcard)

    def test_mention_duplicate_full_name(self) -> None:
        realm = get_realm("zulip")

        def make_user(email: str, full_name: str) -> UserProfile:
            return create_user(
                email=email,
                password="whatever",
                realm=realm,
                full_name=full_name,
            )

        sender_user_profile = self.example_user("othello")
        twin1 = make_user("twin1@example.com", "Mark Twin")
        twin2 = make_user("twin2@example.com", "Mark Twin")
        cordelia = self.example_user("cordelia")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)

        content = f"@**Mark Twin|{twin1.id}**, @**Mark Twin|{twin2.id}** and @**Cordelia, Lear's daughter**, hi."

        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>"
            '<span class="user-mention" '
            f'data-user-id="{twin1.id}">@Mark Twin</span>, '
            '<span class="user-mention" '
            f'data-user-id="{twin2.id}">@Mark Twin</span> and '
            '<span class="user-mention" '
            f'data-user-id="{cordelia.id}">@Cordelia, Lear\'s daughter</span>, '
            "hi.</p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {twin1.id, twin2.id, cordelia.id})

    def test_mention_invalid(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )

        content = "Hey @**Nonexistent User**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content, "<p>Hey @<strong>Nonexistent User</strong></p>"
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def test_user_mention_atomic_string(self) -> None:
        sender_user_profile = self.example_user("othello")
        realm = get_realm("zulip")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        # Create a linkifier.
        url_template = r"https://trac.example.com/ticket/{id}"
        linkifier = RealmFilter(
            realm=realm, pattern=r"#(?P<id>[0-9]{2,8})", url_template=url_template
        )
        linkifier.save()
        self.assertEqual(
            repr(linkifier),
            "<RealmFilter: zulip: #(?P<id>[0-9]{2,8}) https://trac.example.com/ticket/{id}>",
        )
        # Create a user that potentially interferes with the pattern.
        test_user = create_user(
            email="atomic@example.com",
            password="whatever",
            realm=realm,
            full_name="Atomic #123",
        )
        content = "@**Atomic #123**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention" '
            f'data-user-id="{test_user.id}">'
            "@Atomic #123</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {test_user.id})
        content = "@_**Atomic #123**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention silent" '
            f'data-user-id="{test_user.id}">'
            "Atomic #123</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    def create_user_group_for_test(self, user_group_name: str) -> NamedUserGroup:
        othello = self.example_user("othello")
        return check_add_user_group(
            get_realm("zulip"), user_group_name, [othello], acting_user=None
        )

    def test_user_group_mention_single(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id
        user_group = self.create_user_group_for_test("support")

        content = "@**King Hamlet** @*support*"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention" '
            f'data-user-id="{user_id}">'
            "@King Hamlet</span> "
            '<span class="user-group-mention" '
            f'data-user-group-id="{user_group.id}">'
            "@support</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})
        self.assertEqual(rendering_result.mentions_user_group_ids, {user_group.id})

    def test_invalid_user_group_followed_by_valid_mention_single(self) -> None:
        sender_user_profile = self.example_user("othello")
        user_profile = self.example_user("hamlet")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        user_id = user_profile.id
        user_group = self.create_user_group_for_test("support")

        content = "@**King Hamlet** @*Invalid user group* @*support*"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention" '
            f'data-user-id="{user_id}">'
            "@King Hamlet</span> "
            "@<em>Invalid user group</em> "
            '<span class="user-group-mention" '
            f'data-user-group-id="{user_group.id}">'
            "@support</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})
        self.assertEqual(rendering_result.mentions_user_group_ids, {user_group.id})

    def test_user_group_mention_atomic_string(self) -> None:
        sender_user_profile = self.example_user("othello")
        realm = get_realm("zulip")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        user_profile = self.example_user("hamlet")
        # Create a linkifier.
        url_template = r"https://trac.example.com/ticket/{id}"
        linkifier = RealmFilter(
            realm=realm, pattern=r"#(?P<id>[0-9]{2,8})", url_template=url_template
        )
        linkifier.save()
        self.assertEqual(
            repr(linkifier),
            "<RealmFilter: zulip: #(?P<id>[0-9]{2,8}) https://trac.example.com/ticket/{id}>",
        )
        # Create a user-group that potentially interferes with the pattern.
        user_id = user_profile.id
        user_group = self.create_user_group_for_test("support #123")

        content = "@**King Hamlet** @*support #123*"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            '<p><span class="user-mention" '
            f'data-user-id="{user_id}">'
            "@King Hamlet</span> "
            '<span class="user-group-mention" '
            f'data-user-group-id="{user_group.id}">'
            "@support #123</span></p>",
        )
        self.assertEqual(rendering_result.mentions_user_ids, {user_profile.id})
        self.assertEqual(rendering_result.mentions_user_group_ids, {user_group.id})

    def test_possible_user_group_mentions(self) -> None:
        def assert_mentions(content: str, names: Set[str]) -> None:
            self.assertEqual(possible_user_group_mentions(content), names)

        assert_mentions("", set())
        assert_mentions("boring", set())
        assert_mentions("@**all**", set())
        assert_mentions("smush@*steve*smush", set())

        assert_mentions(
            "@*support* Hello @**King Hamlet** and @**Cordelia, Lear's daughter**\n"
            "@**Foo van Barson** @**all**",
            {"support"},
        )

        assert_mentions(
            "Attention @*support*, @*frontend* and @*backend*\ngroups.",
            {"support", "frontend", "backend"},
        )

    def test_user_group_mention_multiple(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        support = self.create_user_group_for_test("support")
        backend = self.create_user_group_for_test("backend")

        content = "@*support* and @*backend*, check this out"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>"
            '<span class="user-group-mention" '
            f'data-user-group-id="{support.id}">'
            "@support</span> "
            "and "
            '<span class="user-group-mention" '
            f'data-user-group-id="{backend.id}">'
            "@backend</span>, "
            "check this out"
            "</p>",
        )

        self.assertEqual(rendering_result.mentions_user_group_ids, {support.id, backend.id})

    def test_user_group_mention_edit(self) -> None:
        sender_user_profile = self.example_user("hamlet")
        user_profile = self.example_user("othello")
        self.create_user_group_for_test("support")
        self.login("hamlet")

        msg_id = self.send_stream_message(
            sender_user_profile, "Denmark", topic_name="editing", content="test"
        )

        def update_message_and_check_flag(content: str, mentioned: bool) -> None:
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "content": content,
                },
            )
            self.assert_json_success(result)
            um = UserMessage.objects.get(
                user_profile_id=user_profile.id,
                message_id=msg_id,
            )
            if mentioned:
                self.assertIn("mentioned", um.flags_list())
            else:
                self.assertNotIn("mentioned", um.flags_list())

        update_message_and_check_flag("@*support*", True)
        update_message_and_check_flag("@*support-invalid* edited", False)
        update_message_and_check_flag("@*support* edited", True)
        update_message_and_check_flag("edited", False)
        update_message_and_check_flag("@*support*", True)
        update_message_and_check_flag("@_*support*", False)

    def test_user_group_mention_invalid(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )

        content = "Hey @*Nonexistent group*"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content, "<p>Hey @<em>Nonexistent group</em></p>"
        )
        self.assertEqual(rendering_result.mentions_user_group_ids, set())

    def test_user_group_silent_mention(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        support = self.create_user_group_for_test("support")

        content = "We'll add you to @_*support* user group."
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content,
            "<p>We'll add you to "
            f'<span class="user-group-mention silent" data-user-group-id="{support.id}">support</span>'
            " user group.</p>",
        )

        self.assertEqual(rendering_result.mentions_user_group_ids, set())

    def test_user_group_mention_in_quotes(self) -> None:
        user_profile = self.example_user("othello")
        message = Message(
            sender=user_profile, sending_client=get_client("test"), realm=user_profile.realm
        )
        backend = self.create_user_group_for_test("backend")

        def assert_silent_mention(content: str) -> None:
            expected = (
                "<blockquote>\n<p>"
                f'<span class="user-group-mention silent" data-user-group-id="{backend.id}">backend</span>'
                "</p>\n</blockquote>"
            )
            rendering_result = render_message_markdown(message, content)
            self.assertEqual(rendering_result.rendered_content, expected)
            self.assertEqual(rendering_result.mentions_user_group_ids, set())

        assert_silent_mention("> @*backend*")
        assert_silent_mention("> @_*backend*")
        assert_silent_mention("```quote\n@*backend*\n```")
        assert_silent_mention("```quote\n@_*backend*\n```")

    def test_system_user_group_mention(self) -> None:
        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        moderators_group = NamedUserGroup.objects.get(
            realm=iago.realm, name=SystemGroups.MODERATORS, is_system_group=True
        )
        content = "@*role:moderators* @**King Hamlet** test message"

        # Owner cannot mention a system user group.
        msg = Message(sender=desdemona, sending_client=get_client("test"), realm=desdemona.realm)
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.mentions_user_ids, {hamlet.id})
        self.assertNotIn(moderators_group, rendering_result.mentions_user_group_ids)

        # Admin belonging to user group also cannot mention a system user group.
        msg = Message(sender=iago, sending_client=get_client("test"), realm=iago.realm)
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(rendering_result.mentions_user_ids, {hamlet.id})
        self.assertNotIn(moderators_group, rendering_result.mentions_user_group_ids)

    def test_stream_single(self) -> None:
        denmark = get_stream("Denmark", get_realm("zulip"))
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        content = "#**Denmark**"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p><a class="stream" data-stream-id="{denmark.id}" href="/#narrow/stream/{denmark.id}-Denmark">#{denmark.name}</a></p>',
        )

    def test_invalid_stream_followed_by_valid_mention(self) -> None:
        denmark = get_stream("Denmark", get_realm("zulip"))
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        content = "#**Invalid** and #**Denmark**"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p>#<strong>Invalid</strong> and <a class="stream" data-stream-id="{denmark.id}" href="/#narrow/stream/{denmark.id}-Denmark">#{denmark.name}</a></p>',
        )

    def test_stream_multiple(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        realm = get_realm("zulip")
        denmark = get_stream("Denmark", realm)
        scotland = get_stream("Scotland", realm)
        content = "Look to #**Denmark** and #**Scotland**, there something"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            "<p>Look to "
            '<a class="stream" '
            f'data-stream-id="{denmark.id}" '
            f'href="/#narrow/stream/{denmark.id}-Denmark">#{denmark.name}</a> and '
            '<a class="stream" '
            f'data-stream-id="{scotland.id}" '
            f'href="/#narrow/stream/{scotland.id}-Scotland">#{scotland.name}</a>, '
            "there something</p>",
        )

    def test_stream_case_sensitivity(self) -> None:
        realm = get_realm("zulip")
        case_sens = self.make_stream(stream_name="CaseSens", realm=realm)
        sender_user_profile = self.example_user("othello")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        content = "#**CaseSens**"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p><a class="stream" data-stream-id="{case_sens.id}" href="/#narrow/stream/{case_sens.id}-{case_sens.name}">#{case_sens.name}</a></p>',
        )

    def test_stream_case_sensitivity_nonmatching(self) -> None:
        """#StreamName requires the stream be spelled with the correct case
        currently.  If we change that in the future, we'll need to change this
        test."""
        realm = get_realm("zulip")
        self.make_stream(stream_name="CaseSens", realm=realm)
        sender_user_profile = self.example_user("othello")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        content = "#**casesens**"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            "<p>#<strong>casesens</strong></p>",
        )

    def test_topic_single(self) -> None:
        denmark = get_stream("Denmark", get_realm("zulip"))
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        content = "#**Denmark>some topic**"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p><a class="stream-topic" data-stream-id="{denmark.id}" href="/#narrow/stream/{denmark.id}-Denmark/topic/some.20topic">#{denmark.name} &gt; some topic</a></p>',
        )

    def test_topic_atomic_string(self) -> None:
        realm = get_realm("zulip")
        # Create a linkifier.
        sender_user_profile = self.example_user("othello")
        url_template = r"https://trac.example.com/ticket/{id}"
        linkifier = RealmFilter(
            realm=realm, pattern=r"#(?P<id>[0-9]{2,8})", url_template=url_template
        )
        linkifier.save()
        self.assertEqual(
            repr(linkifier),
            "<RealmFilter: zulip: #(?P<id>[0-9]{2,8}) https://trac.example.com/ticket/{id}>",
        )
        # Create a topic link that potentially interferes with the pattern.
        denmark = get_stream("Denmark", realm)
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        content = "#**Denmark>#1234**"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p><a class="stream-topic" data-stream-id="{denmark.id}" href="/#narrow/stream/{denmark.id}-Denmark/topic/.231234">#{denmark.name} &gt; #1234</a></p>',
        )

    def test_topic_multiple(self) -> None:
        denmark = get_stream("Denmark", get_realm("zulip"))
        scotland = get_stream("Scotland", get_realm("zulip"))
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        content = "This has two links: #**Denmark>some topic** and #**Scotland>other topic**."
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            "<p>This has two links: "
            f'<a class="stream-topic" data-stream-id="{denmark.id}" '
            f'href="/#narrow/stream/{denmark.id}-{denmark.name}/topic/some.20topic">'
            f"#{denmark.name} &gt; some topic</a>"
            " and "
            f'<a class="stream-topic" data-stream-id="{scotland.id}" '
            f'href="/#narrow/stream/{scotland.id}-{scotland.name}/topic/other.20topic">'
            f"#{scotland.name} &gt; other topic</a>"
            ".</p>",
        )

    def test_possible_stream_names(self) -> None:
        content = """#**test here**
            This mentions #**Denmark** too.
            #**garçon** #**천국** @**Ignore Person**
        """
        self.assertEqual(
            possible_linked_stream_names(content),
            {"test here", "Denmark", "garçon", "천국"},
        )

    def test_stream_unicode(self) -> None:
        realm = get_realm("zulip")
        uni = self.make_stream(stream_name="привет", realm=realm)
        sender_user_profile = self.example_user("othello")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        content = "#**привет**"
        quoted_name = ".D0.BF.D1.80.D0.B8.D0.B2.D0.B5.D1.82"
        href = f"/#narrow/stream/{uni.id}-{quoted_name}"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p><a class="stream" data-stream-id="{uni.id}" href="{href}">#{uni.name}</a></p>',
        )

    def test_stream_atomic_string(self) -> None:
        realm = get_realm("zulip")
        # Create a linkifier.
        sender_user_profile = self.example_user("othello")
        url_template = r"https://trac.example.com/ticket/{id}"
        linkifier = RealmFilter(
            realm=realm, pattern=r"#(?P<id>[0-9]{2,8})", url_template=url_template
        )
        linkifier.save()
        self.assertEqual(
            repr(linkifier),
            "<RealmFilter: zulip: #(?P<id>[0-9]{2,8}) https://trac.example.com/ticket/{id}>",
        )
        # Create a stream that potentially interferes with the pattern.
        stream = self.make_stream(stream_name="Stream #1234", realm=realm)
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"), realm=realm)
        content = "#**Stream #1234**"
        href = f"/#narrow/stream/{stream.id}-Stream-.231234"
        self.assertEqual(
            render_message_markdown(msg, content).rendered_content,
            f'<p><a class="stream" data-stream-id="{stream.id}" href="{href}">#{stream.name}</a></p>',
        )

    def test_stream_invalid(self) -> None:
        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )

        content = "There #**Nonexistentstream**"
        rendering_result = render_message_markdown(msg, content)
        self.assertEqual(
            rendering_result.rendered_content, "<p>There #<strong>Nonexistentstream</strong></p>"
        )
        self.assertEqual(rendering_result.mentions_user_ids, set())

    @override_settings(THUMBNAIL_IMAGES=True)
    def test_image_preview_title(self) -> None:
        msg = "[My favorite image](https://example.com/testimage.png)"
        converted = markdown_convert_wrapper(msg)
        self.assertEqual(
            converted,
            "<p>"
            '<a href="https://example.com/testimage.png">My favorite image</a>'
            "</p>\n"
            '<div class="message_inline_image">'
            '<a href="https://example.com/testimage.png" title="My favorite image">'
            '<img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fexample.com%2Ftestimage.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fexample.com%2Ftestimage.png&amp;size=thumbnail">'
            "</a>"
            "</div>",
        )

    def test_mit_rendering(self) -> None:
        """Test the Markdown configs for the MIT Zephyr mirroring system;
        verifies almost all inline patterns are disabled, but
        inline_interesting_links is still enabled"""
        msg = "**test**"
        realm = get_realm("zephyr")
        client = get_client("zephyr_mirror")
        message = Message(sending_client=client, sender=self.mit_user("sipbtest"))
        converted = markdown_convert(msg, message_realm=realm, message=message)
        self.assertEqual(
            converted.rendered_content,
            "<p>**test**</p>",
        )
        msg = "* test"
        converted = markdown_convert(msg, message_realm=realm, message=message)
        self.assertEqual(
            converted.rendered_content,
            "<p>* test</p>",
        )
        msg = "https://lists.debian.org/debian-ctte/2014/02/msg00173.html"
        converted = markdown_convert(msg, message_realm=realm, message=message)
        self.assertEqual(
            converted.rendered_content,
            '<p><a href="https://lists.debian.org/debian-ctte/2014/02/msg00173.html">https://lists.debian.org/debian-ctte/2014/02/msg00173.html</a></p>',
        )

    def test_url_to_a(self) -> None:
        url = "javascript://example.com/invalidURL"
        converted = url_to_a(db_data=None, url=url, text=url)
        self.assertEqual(
            converted,
            "javascript://example.com/invalidURL",
        )

    def test_disabled_code_block_processor(self) -> None:
        msg = (
            "Hello,\n\n"
            "    I am writing this message to test something. I am writing this message to test"
            " something."
        )
        converted = markdown_convert_wrapper(msg)
        expected_output = (
            "<p>Hello,</p>\n"
            '<div class="codehilite"><pre><span></span><code>I am writing this message to test'
            " something. I am writing this message to test something.\n"
            "</code></pre></div>"
        )
        self.assertEqual(converted, expected_output)

        realm = do_create_realm(
            string_id="code_block_processor_test", name="code_block_processor_test"
        )
        maybe_update_markdown_engines(realm.id, True)
        rendering_result = markdown_convert(msg, message_realm=realm, email_gateway=True)
        expected_output = (
            "<p>Hello,</p>\n"
            "<p>I am writing this message to test something. I am writing this message to test"
            " something.</p>"
        )
        self.assertEqual(rendering_result.rendered_content, expected_output)

    def test_normal_link(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user("othello")
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        msg = "http://example.com/#settings/"

        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            '<p><a href="http://example.com/#settings/">http://example.com/#settings/</a></p>',
        )

    def test_relative_link(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user("othello")
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))

        msg = "http://zulip.testserver/#narrow/stream/999-hello"
        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            '<p><a href="#narrow/stream/999-hello">http://zulip.testserver/#narrow/stream/999-hello</a></p>',
        )

        msg = f"http://zulip.testserver/user_uploads/{realm.id}/ff/file.txt"
        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            f'<p><a href="user_uploads/{realm.id}/ff/file.txt">http://zulip.testserver/user_uploads/{realm.id}/ff/file.txt</a></p>',
        )

        msg = "http://zulip.testserver/not:relative"
        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            '<p><a href="http://zulip.testserver/not:relative">http://zulip.testserver/not:relative</a></p>',
        )

    def test_relative_link_streams_page(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user("othello")
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        msg = "http://zulip.testserver/#channels/all"

        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            '<p><a href="#channels/all">http://zulip.testserver/#channels/all</a></p>',
        )

    def test_md_relative_link(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user("othello")
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))

        msg = "[hello](http://zulip.testserver/#narrow/stream/999-hello)"
        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            '<p><a href="#narrow/stream/999-hello">hello</a></p>',
        )

        msg = f"[hello](http://zulip.testserver/user_uploads/{realm.id}/ff/file.txt)"
        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            f'<p><a href="user_uploads/{realm.id}/ff/file.txt">hello</a></p>',
        )

        msg = "[hello](http://zulip.testserver/not:relative)"
        self.assertEqual(
            markdown_convert(msg, message_realm=realm, message=message).rendered_content,
            '<p><a href="http://zulip.testserver/not:relative">hello</a></p>',
        )

    def test_html_entity_conversion(self) -> None:
        msg = """\
            Test raw: Hello, &copy;
            Test inline code: `&copy;`

            Test fenced code:
            ```
            &copy;
            &copy;
            ```

            Test quote:
            ~~~quote
            &copy;
            ~~~

            Test a list:
            * &copy;
            * `&copy;`
            * ```&copy;```

            Test an indented block:

                &copy;"""

        expected_output = """\
            <p>Test raw: Hello, &copy;<br>
            Test inline code: <code>&amp;copy;</code></p>
            <p>Test fenced code:</p>
            <div class="codehilite"><pre><span></span><code>&amp;copy;
            &amp;copy;
            </code></pre></div>
            <p>Test quote:</p>
            <blockquote>
            <p>&copy;</p>
            </blockquote>
            <p>Test a list:</p>
            <ul>
            <li>&copy;</li>
            <li><code>&amp;copy;</code></li>
            <li><code>&amp;copy;</code></li>
            </ul>
            <p>Test an indented block:</p>
            <div class="codehilite"><pre><span></span><code>&amp;copy;
            </code></pre></div>"""

        converted = markdown_convert_wrapper(dedent(msg))
        self.assertEqual(converted, dedent(expected_output))


class MarkdownApiTests(ZulipTestCase):
    def test_render_message_api(self) -> None:
        content = "That is a **bold** statement"
        result = self.api_post(
            self.example_user("othello"),
            "/api/v1/messages/render",
            dict(content=content),
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(
            response_dict["rendered"], "<p>That is a <strong>bold</strong> statement</p>"
        )

    def test_render_mention_stream_api(self) -> None:
        """Determines whether we're correctly passing the realm context"""
        content = "This mentions #**Denmark** and @**King Hamlet**."
        result = self.api_post(
            self.example_user("othello"),
            "/api/v1/messages/render",
            dict(content=content),
        )
        response_dict = self.assert_json_success(result)
        user_id = self.example_user("hamlet").id
        stream_id = get_stream("Denmark", get_realm("zulip")).id
        self.assertEqual(
            response_dict["rendered"],
            f'<p>This mentions <a class="stream" data-stream-id="{stream_id}" href="/#narrow/stream/{stream_id}-Denmark">#Denmark</a> and <span class="user-mention" data-user-id="{user_id}">@King Hamlet</span>.</p>',
        )


class MarkdownErrorTests(ZulipTestCase):
    def test_markdown_error_handling(self) -> None:
        with self.simulated_markdown_failure():
            with self.assertRaises(MarkdownRenderingError):
                markdown_convert_wrapper("")

    def test_send_message_errors(self) -> None:
        message = "whatever"
        with self.simulated_markdown_failure():
            # We don't use assertRaisesRegex because it seems to not
            # handle i18n properly here on some systems.
            with self.assertRaises(JsonableError):
                self.send_stream_message(self.example_user("othello"), "Denmark", message)

    @override_settings(MAX_MESSAGE_LENGTH=10)
    def test_ultra_long_rendering(self) -> None:
        """A rendered message with an ultra-long length (> 100 * MAX_MESSAGE_LENGTH)
        throws an exception"""
        msg = "mock rendered message\n" * 10 * settings.MAX_MESSAGE_LENGTH

        with mock.patch("zerver.lib.markdown.unsafe_timeout", return_value=msg), mock.patch(
            "zerver.lib.markdown.markdown_logger"
        ):
            with self.assertRaises(MarkdownRenderingError):
                markdown_convert_wrapper(msg)

    def test_curl_code_block_validation(self) -> None:
        processor = SimulatedFencedBlockPreprocessor(Markdown())
        processor.run_content_validators = True

        markdown_input = [
            "``` curl",
            "curl {{ api_url }}/v1/register",
            "    -u BOT_EMAIL_ADDRESS:BOT_API_KEY",
            '    -d "queue_id=fb67bf8a-c031-47cc-84cf-ed80accacda8"',
            "```",
        ]

        with self.assertRaises(MarkdownRenderingError):
            processor.run(markdown_input)

    def test_curl_code_block_without_validation(self) -> None:
        processor = SimulatedFencedBlockPreprocessor(Markdown())

        markdown_input = [
            "``` curl",
            "curl {{ api_url }}/v1/register",
            "    -u BOT_EMAIL_ADDRESS:BOT_API_KEY",
            '    -d "queue_id=fb67bf8a-c031-47cc-84cf-ed80accacda8"',
            "```",
        ]
        expected = [
            "",
            "**curl:curl {{ api_url }}/v1/register",
            "    -u BOT_EMAIL_ADDRESS:BOT_API_KEY",
            '    -d "queue_id=fb67bf8a-c031-47cc-84cf-ed80accacda8"**',
            "",
            "",
        ]

        result = processor.run(markdown_input)
        self.assertEqual(result, expected)


class MarkdownEmojiTest(ZulipTestCase):
    def test_all_emoji_match_regex(self) -> None:
        non_matching_emoji = [
            emoji
            for codepoint in codepoint_to_name
            if not POSSIBLE_EMOJI_RE.fullmatch(emoji := hex_codepoint_to_emoji(codepoint))
        ]
        self.assertEqual(
            non_matching_emoji,
            # unqualified numbers in boxes shouldn't be converted to emoji images, so this is fine
            ["#⃣", "*⃣", "0⃣", "1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣"],
        )
