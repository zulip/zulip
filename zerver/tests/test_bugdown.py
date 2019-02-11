# -*- coding: utf-8 -*-
from django.conf import settings
from django.test import TestCase, override_settings

from zerver.lib import bugdown
from zerver.lib.actions import (
    do_set_user_display_setting,
    do_remove_realm_emoji,
    do_set_alert_words,
)
from zerver.lib.alert_words import get_alert_word_automaton
from zerver.lib.create_user import create_user
from zerver.lib.emoji import get_emoji_url
from zerver.lib.exceptions import BugdownRenderingException
from zerver.lib.mention import possible_mentions, possible_user_group_mentions
from zerver.lib.message import render_markdown
from zerver.lib.request import (
    JsonableError,
)
from zerver.lib.user_groups import create_user_group
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow
from zerver.lib import mdiff
from zerver.lib.tex import render_tex
from zerver.models import (
    realm_in_local_realm_filters_cache,
    flush_per_request_caches,
    flush_realm_filter,
    get_client,
    get_realm,
    get_stream,
    realm_filters_for_realm,
    MAX_MESSAGE_LENGTH,
    Message,
    Stream,
    Realm,
    RealmEmoji,
    RealmFilter,
    UserProfile,
    UserGroup,
)

import copy
import mock
import os
import ujson

from typing import cast, Any, Dict, List, Optional, Set, Tuple

class FakeMessage:
    pass

class FencedBlockPreprocessorTest(TestCase):
    def test_simple_quoting(self) -> None:
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)
        markdown = [
            '~~~ quote',
            'hi',
            'bye',
            '',
            ''
        ]
        expected = [
            '',
            '> hi',
            '> bye',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_serial_quoting(self) -> None:
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)
        markdown = [
            '~~~ quote',
            'hi',
            '~~~',
            '',
            '~~~ quote',
            'bye',
            '',
            ''
        ]
        expected = [
            '',
            '> hi',
            '',
            '',
            '',
            '> bye',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_serial_code(self) -> None:
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code  # type: ignore # mypy doesn't allow monkey-patching functions
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**'  # type: ignore # https://github.com/python/mypy/issues/708

        markdown = [
            '``` .py',
            'hello()',
            '```',
            '',
            '```vb.net',
            'goodbye()',
            '```',
            '',
            '```c#',
            'weirdchar()',
            '```',
            ''
        ]
        expected = [
            '',
            '**py:hello()**',
            '',
            '',
            '',
            '**vb.net:goodbye()**',
            '',
            '',
            '',
            '**c#:weirdchar()**',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_nested_code(self) -> None:
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code  # type: ignore # mypy doesn't allow monkey-patching functions
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**'  # type: ignore # https://github.com/python/mypy/issues/708

        markdown = [
            '~~~ quote',
            'hi',
            '``` .py',
            'hello()',
            '```',
            '',
            ''
        ]
        expected = [
            '',
            '> hi',
            '',
            '> **py:hello()**',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

def bugdown_convert(content: str) -> str:
    message = cast(Message, FakeMessage())
    message.content = content
    message.id = 999
    return bugdown.convert(
        content=content,
        message_realm=get_realm('zulip'),
        message=message
    )

class BugdownMiscTest(ZulipTestCase):
    def test_diffs_work_as_expected(self) -> None:
        str1 = "<p>The quick brown fox jumps over the lazy dog.  Animal stories are fun, yeah</p>"
        str2 = "<p>The fast fox jumps over the lazy dogs and cats.  Animal stories are fun</p>"
        expected_diff = "\u001b[34m-\u001b[0m <p>The \u001b[33mquick brown\u001b[0m fox jumps over the lazy dog.  Animal stories are fun\u001b[31m, yeah\u001b[0m</p>\n\u001b[34m+\u001b[0m <p>The \u001b[33mfast\u001b[0m fox jumps over the lazy dog\u001b[32ms and cats\u001b[0m.  Animal stories are fun</p>\n"
        self.assertEqual(mdiff.diff_strings(str1, str2), expected_diff)

    def test_get_possible_mentions_info(self) -> None:
        realm = get_realm('zulip')

        def make_user(email: str, full_name: str) -> UserProfile:
            return create_user(
                email=email,
                password='whatever',
                realm=realm,
                full_name=full_name,
                short_name='whatever',
            )

        fred1 = make_user('fred1@example.com', 'Fred Flintstone')
        fred1.is_active = False
        fred1.save()

        fred2 = make_user('fred2@example.com', 'Fred Flintstone')

        fred3 = make_user('fred3@example.com', 'Fred Flintstone')
        fred3.is_active = False
        fred3.save()

        fred4 = make_user('fred4@example.com', 'Fred Flintstone')

        lst = bugdown.get_possible_mentions_info(realm.id, {'Fred Flintstone', 'cordelia LEAR', 'Not A User'})
        set_of_names = set(map(lambda x: x['full_name'].lower(), lst))
        self.assertEqual(set_of_names, {'fred flintstone', 'cordelia lear'})

        by_id = {
            row['id']: row
            for row in lst
        }
        self.assertEqual(by_id.get(fred2.id), dict(
            email='fred2@example.com',
            full_name='Fred Flintstone',
            id=fred2.id
        ))
        self.assertEqual(by_id.get(fred4.id), dict(
            email='fred4@example.com',
            full_name='Fred Flintstone',
            id=fred4.id
        ))

    def test_mention_data(self) -> None:
        realm = get_realm('zulip')
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        content = '@**King Hamlet** @**Cordelia lear**'
        mention_data = bugdown.MentionData(realm.id, content)
        self.assertEqual(mention_data.get_user_ids(), {hamlet.id, cordelia.id})
        self.assertEqual(mention_data.get_user_by_id(hamlet.id), dict(
            email=hamlet.email,
            full_name=hamlet.full_name,
            id=hamlet.id
        ))

        user = mention_data.get_user_by_name('king hamLET')
        assert(user is not None)
        self.assertEqual(user['email'], hamlet.email)

    def test_invalid_katex_path(self) -> None:
        with self.settings(STATIC_ROOT="/invalid/path"):
            with mock.patch('logging.error') as mock_logger:
                render_tex("random text")
                mock_logger.assert_called_with("Cannot find KaTeX for latex rendering!")

class BugdownTest(ZulipTestCase):
    def setUp(self) -> None:
        bugdown.clear_state_for_testing()

    def assertEqual(self, first: Any, second: Any, msg: str = "") -> None:
        if isinstance(first, str) and isinstance(second, str):
            if first != second:
                raise AssertionError("Actual and expected outputs do not match; showing diff.\n" +
                                     mdiff.diff_strings(first, second) + msg)
        else:
            super().assertEqual(first, second)

    def load_bugdown_tests(self) -> Tuple[Dict[str, Any], List[List[str]]]:
        test_fixtures = {}
        data_file = open(os.path.join(os.path.dirname(__file__), 'fixtures/markdown_test_cases.json'), 'r')
        data = ujson.loads('\n'.join(data_file.readlines()))
        for test in data['regular_tests']:
            test_fixtures[test['name']] = test

        return test_fixtures, data['linkify_tests']

    def test_bugdown_no_ignores(self) -> None:
        # We do not want any ignored tests to be committed and merged.
        format_tests, linkify_tests = self.load_bugdown_tests()
        for name, test in format_tests.items():
            message = 'Test "%s" shouldn\'t be ignored.' % (name,)
            is_ignored = test.get('ignore', False)
            self.assertFalse(is_ignored, message)

    @slow("Aggregate of runs dozens of individual markdown tests")
    def test_bugdown_fixtures(self) -> None:
        format_tests, linkify_tests = self.load_bugdown_tests()
        valid_keys = set(["name", "input", "expected_output",
                          "backend_only_rendering",
                          "marked_expected_output", "text_content",
                          "translate_emoticons", "ignore"])

        for name, test in format_tests.items():
            # Check that there aren't any unexpected keys as those are often typos
            self.assertEqual(len(set(test.keys()) - valid_keys), 0)

            # Ignore tests if specified
            if test.get('ignore', False):
                continue  # nocoverage

            if test.get('translate_emoticons', False):
                # Create a userprofile and send message with it.
                user_profile = self.example_user('othello')
                do_set_user_display_setting(user_profile, 'translate_emoticons', True)
                msg = Message(sender=user_profile, sending_client=get_client("test"))
                converted = render_markdown(msg, test['input'])
            else:
                converted = bugdown_convert(test['input'])

            with self.subTest(markdown_test_case=name):
                print("Running Bugdown test %s" % (name,))
                self.assertEqual(converted, test['expected_output'])

        def replaced(payload: str, url: str, phrase: str='') -> str:
            target = " target=\"_blank\""
            if url[:4] == 'http':
                href = url
            elif '@' in url:
                href = 'mailto:' + url
                target = ""
            else:
                href = 'http://' + url
            return payload % ("<a href=\"%s\"%s title=\"%s\">%s</a>" % (href, target, href, url),)

        print("Running Bugdown Linkify tests")
        with mock.patch('zerver.lib.url_preview.preview.link_embed_data_from_cache', return_value=None):
            for inline_url, reference, url in linkify_tests:
                try:
                    match = replaced(reference, url, phrase=inline_url)
                except TypeError:
                    match = reference
                converted = bugdown_convert(inline_url)
                self.assertEqual(match, converted)

    def test_inline_file(self) -> None:
        msg = 'Check out this file file:///Volumes/myserver/Users/Shared/pi.py'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>Check out this file <a href="file:///Volumes/myserver/Users/Shared/pi.py" target="_blank" title="file:///Volumes/myserver/Users/Shared/pi.py">file:///Volumes/myserver/Users/Shared/pi.py</a></p>')

        bugdown.clear_state_for_testing()
        with self.settings(ENABLE_FILE_LINKS=False):
            realm = Realm.objects.create(string_id='file_links_test')
            bugdown.maybe_update_markdown_engines(realm.id, False)
            converted = bugdown.convert(msg, message_realm=realm)
            self.assertEqual(converted, '<p>Check out this file file:///Volumes/myserver/Users/Shared/pi.py</p>')

    def test_inline_bitcoin(self) -> None:
        msg = 'To bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or not to bitcoin'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>To <a href="bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" target="_blank" title="bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa">bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa</a> or not to bitcoin</p>')

    def test_inline_youtube(self) -> None:
        msg = 'Check out the debate: http://www.youtube.com/watch?v=hx1mjT73xYE'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="youtube-video message_inline_image"><a data-id="hx1mjT73xYE" href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg"></a></div>')

        msg = 'http://www.youtube.com/watch?v=hx1mjT73xYE'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p><a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="youtube-video message_inline_image"><a data-id="hx1mjT73xYE" href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg"></a></div>')

    def test_inline_vimeo(self) -> None:
        msg = 'Check out the debate: https://vimeo.com/246979354'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Check out the debate: <a href="https://vimeo.com/246979354" target="_blank" title="https://vimeo.com/246979354">https://vimeo.com/246979354</a></p>')

        msg = 'https://vimeo.com/246979354'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p><a href="https://vimeo.com/246979354" target="_blank" title="https://vimeo.com/246979354">https://vimeo.com/246979354</a></p>')

    @override_settings(INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_thumbnail_url(self):
        # type: () -> None
        msg = '[foobar](/user_uploads/2/50/w2G6ok9kr8AMCQCTNAUOFMln/IMG_0677.JPG)'
        thumbnail_img = '<img data-src-fullsize="/thumbnail?url=user_uploads%2F2%2F50%2Fw2G6ok9kr8AMCQCTNAUOFMln%2FIMG_0677.JPG&amp;size=full" src="/thumbnail?url=user_uploads%2F2%2F50%2Fw2G6ok9kr8AMCQCTNAUOFMln%2FIMG_0677.JPG&amp;size=thumbnail"><'
        converted = bugdown_convert(msg)
        self.assertIn(thumbnail_img, converted)

        msg = 'https://www.google.com/images/srpr/logo4w.png'
        thumbnail_img = '<img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=thumbnail">'
        converted = bugdown_convert(msg)
        self.assertIn(thumbnail_img, converted)

        msg = 'www.google.com/images/srpr/logo4w.png'
        thumbnail_img = '<img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=thumbnail">'
        converted = bugdown_convert(msg)
        self.assertIn(thumbnail_img, converted)

        msg = 'https://www.google.com/images/srpr/logo4w.png'
        thumbnail_img = '<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://www.google.com/images/srpr/logo4w.png"></a></div>'
        with self.settings(THUMBNAIL_IMAGES=False):
            converted = bugdown_convert(msg)
        self.assertIn(thumbnail_img, converted)

        # Any url which is not an external link and doesn't start with
        # /user_uploads/ is not thumbnailed
        msg = '[foobar](/static/images/cute/turtle.png)'
        thumbnail_img = '<div class="message_inline_image"><a href="/static/images/cute/turtle.png" target="_blank" title="foobar"><img src="/static/images/cute/turtle.png"></a></div>'
        converted = bugdown_convert(msg)
        self.assertIn(thumbnail_img, converted)

        msg = '[foobar](/user_avatars/2/emoji/images/50.png)'
        thumbnail_img = '<div class="message_inline_image"><a href="/user_avatars/2/emoji/images/50.png" target="_blank" title="foobar"><img src="/user_avatars/2/emoji/images/50.png"></a></div>'
        converted = bugdown_convert(msg)
        self.assertIn(thumbnail_img, converted)

    @override_settings(INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_preview(self):
        # type: () -> None
        with_preview = '<div class="message_inline_image"><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg" target="_blank" title="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fcdn.wallpapersafari.com%2F13%2F6%2F16eVjx.jpeg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fcdn.wallpapersafari.com%2F13%2F6%2F16eVjx.jpeg&amp;size=thumbnail"></a></div>'
        without_preview = '<p><a href="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg" target="_blank" title="http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg">http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg</a></p>'
        content = 'http://cdn.wallpapersafari.com/13/6/16eVjx.jpeg'

        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        converted = render_markdown(msg, content)
        self.assertEqual(converted, with_preview)

        realm = msg.get_realm()
        setattr(realm, 'inline_image_preview', False)
        realm.save()

        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        converted = render_markdown(msg, content)
        self.assertEqual(converted, without_preview)

    @override_settings(INLINE_IMAGE_PREVIEW=True)
    def test_inline_image_preview_order(self) -> None:
        content = 'http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg\nhttp://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg\nhttp://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg'
        expected = '<p><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg</a><br>\n<a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg</a><br>\n<a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg">http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg</a></p>\n<div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=thumbnail"></a></div><div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_02.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_02.jpg&amp;size=thumbnail"></a></div><div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=thumbnail"></a></div>'

        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        converted = render_markdown(msg, content)
        self.assertEqual(converted, expected)

        content = 'http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg\n\n>http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg\n\n* http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg\n* https://www.google.com/images/srpr/logo4w.png'
        expected = '<div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_01.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_01.jpg&amp;size=thumbnail"></a></div><blockquote>\n<div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_02.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_02.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_02.jpg&amp;size=thumbnail"></a></div></blockquote>\n<ul>\n<li><div class="message_inline_image"><a href="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg" target="_blank" title="http://imaging.nikon.com/lineup/dslr/df/img/sample/img_03.jpg"><img data-src-fullsize="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=full" src="/thumbnail?url=http%3A%2F%2Fimaging.nikon.com%2Flineup%2Fdslr%2Fdf%2Fimg%2Fsample%2Fimg_03.jpg&amp;size=thumbnail"></a></div></li>\n<li><div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fwww.google.com%2Fimages%2Fsrpr%2Flogo4w.png&amp;size=thumbnail"></a></div></li>\n</ul>'

        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        converted = render_markdown(msg, content)
        self.assertEqual(converted, expected)

        content = 'Test 1\n[21136101110_1dde1c1a7e_o.jpg](/user_uploads/1/6d/F1PX6u16JA2P-nK45PyxHIYZ/21136101110_1dde1c1a7e_o.jpg) \n\nNext Image\n[IMG_20161116_023910.jpg](/user_uploads/1/69/sh7L06e7uH7NaX6d5WFfVYQp/IMG_20161116_023910.jpg) \n\nAnother Screenshot\n[Screenshot-from-2016-06-01-16-22-42.png](/user_uploads/1/70/_aZmIEWaN1iUaxwkDjkO7bpj/Screenshot-from-2016-06-01-16-22-42.png)'
        expected = '<p>Test 1<br>\n<a href="/user_uploads/1/6d/F1PX6u16JA2P-nK45PyxHIYZ/21136101110_1dde1c1a7e_o.jpg" target="_blank" title="21136101110_1dde1c1a7e_o.jpg">21136101110_1dde1c1a7e_o.jpg</a> </p>\n<div class="message_inline_image"><a href="/user_uploads/1/6d/F1PX6u16JA2P-nK45PyxHIYZ/21136101110_1dde1c1a7e_o.jpg" target="_blank" title="21136101110_1dde1c1a7e_o.jpg"><img data-src-fullsize="/thumbnail?url=user_uploads%2F1%2F6d%2FF1PX6u16JA2P-nK45PyxHIYZ%2F21136101110_1dde1c1a7e_o.jpg&amp;size=full" src="/thumbnail?url=user_uploads%2F1%2F6d%2FF1PX6u16JA2P-nK45PyxHIYZ%2F21136101110_1dde1c1a7e_o.jpg&amp;size=thumbnail"></a></div><p>Next Image<br>\n<a href="/user_uploads/1/69/sh7L06e7uH7NaX6d5WFfVYQp/IMG_20161116_023910.jpg" target="_blank" title="IMG_20161116_023910.jpg">IMG_20161116_023910.jpg</a> </p>\n<div class="message_inline_image"><a href="/user_uploads/1/69/sh7L06e7uH7NaX6d5WFfVYQp/IMG_20161116_023910.jpg" target="_blank" title="IMG_20161116_023910.jpg"><img data-src-fullsize="/thumbnail?url=user_uploads%2F1%2F69%2Fsh7L06e7uH7NaX6d5WFfVYQp%2FIMG_20161116_023910.jpg&amp;size=full" src="/thumbnail?url=user_uploads%2F1%2F69%2Fsh7L06e7uH7NaX6d5WFfVYQp%2FIMG_20161116_023910.jpg&amp;size=thumbnail"></a></div><p>Another Screenshot<br>\n<a href="/user_uploads/1/70/_aZmIEWaN1iUaxwkDjkO7bpj/Screenshot-from-2016-06-01-16-22-42.png" target="_blank" title="Screenshot-from-2016-06-01-16-22-42.png">Screenshot-from-2016-06-01-16-22-42.png</a></p>\n<div class="message_inline_image"><a href="/user_uploads/1/70/_aZmIEWaN1iUaxwkDjkO7bpj/Screenshot-from-2016-06-01-16-22-42.png" target="_blank" title="Screenshot-from-2016-06-01-16-22-42.png"><img data-src-fullsize="/thumbnail?url=user_uploads%2F1%2F70%2F_aZmIEWaN1iUaxwkDjkO7bpj%2FScreenshot-from-2016-06-01-16-22-42.png&amp;size=full" src="/thumbnail?url=user_uploads%2F1%2F70%2F_aZmIEWaN1iUaxwkDjkO7bpj%2FScreenshot-from-2016-06-01-16-22-42.png&amp;size=thumbnail"></a></div>'

        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        converted = render_markdown(msg, content)
        self.assertEqual(converted, expected)

    @override_settings(INLINE_IMAGE_PREVIEW=False)
    def test_image_preview_enabled(self) -> None:
        ret = bugdown.image_preview_enabled()
        self.assertEqual(ret, False)

        settings.INLINE_IMAGE_PREVIEW = True

        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm = message.get_realm()

        ret = bugdown.image_preview_enabled()
        self.assertEqual(ret, True)

        ret = bugdown.image_preview_enabled(no_previews=True)
        self.assertEqual(ret, False)

        ret = bugdown.image_preview_enabled(message, realm)
        self.assertEqual(ret, True)

        ret = bugdown.image_preview_enabled(message)
        self.assertEqual(ret, True)

        ret = bugdown.image_preview_enabled(message, realm,
                                            no_previews=True)
        self.assertEqual(ret, False)

        ret = bugdown.image_preview_enabled(message, no_previews=True)
        self.assertEqual(ret, False)

    @override_settings(INLINE_URL_EMBED_PREVIEW=False)
    def test_url_embed_preview_enabled(self) -> None:
        sender_user_profile = self.example_user('othello')
        message = copy.deepcopy(Message(sender=sender_user_profile, sending_client=get_client("test")))
        realm = message.get_realm()

        ret = bugdown.url_embed_preview_enabled()
        self.assertEqual(ret, False)

        settings.INLINE_URL_EMBED_PREVIEW = True

        ret = bugdown.url_embed_preview_enabled()
        self.assertEqual(ret, True)

        ret = bugdown.image_preview_enabled(no_previews=True)
        self.assertEqual(ret, False)

        ret = bugdown.url_embed_preview_enabled(message, realm)
        self.assertEqual(ret, True)
        ret = bugdown.url_embed_preview_enabled(message)
        self.assertEqual(ret, True)

        ret = bugdown.url_embed_preview_enabled(message, no_previews=True)
        self.assertEqual(ret, False)

    def test_inline_dropbox(self) -> None:
        msg = 'Look at how hilarious our old office was: https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG'
        image_info = {'image': 'https://photos-4.dropbox.com/t/2/AABIre1oReJgPYuc_53iv0IHq1vUzRaDg2rrCfTpiWMccQ/12/129/jpeg/1024x1024/2/_/0/4/IMG_0923.JPG/CIEBIAEgAiAHKAIoBw/ymdijjcg67hv2ta/AABz2uuED1ox3vpWWvMpBxu6a/IMG_0923.JPG', 'desc': 'Shared with Dropbox', 'title': 'IMG_0923.JPG'}
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=image_info):
            converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at how hilarious our old office was: <a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" target="_blank" title="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG">https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" target="_blank" title="IMG_0923.JPG"><img src="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG?dl=1"></a></div>')

        msg = 'Look at my hilarious drawing folder: https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl='
        image_info = {'image': 'https://cf.dropboxstatic.com/static/images/icons128/folder_dropbox.png', 'desc': 'Shared with Dropbox', 'title': 'Saves'}
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=image_info):
            converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at my hilarious drawing folder: <a href="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=" target="_blank" title="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=">https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=</a></p>\n<div class="message_inline_ref"><a href="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=" target="_blank" title="Saves"><img src="https://cf.dropboxstatic.com/static/images/icons128/folder_dropbox.png"></a><div><div class="message_inline_image_title">Saves</div><desc class="message_inline_image_desc"></desc></div></div>')

    def test_inline_dropbox_preview(self) -> None:
        # Test photo album previews
        msg = 'https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5'
        image_info = {'image': 'https://photos-6.dropbox.com/t/2/AAAlawaeD61TyNewO5vVi-DGf2ZeuayfyHFdNTNzpGq-QA/12/271544745/jpeg/1024x1024/2/_/0/5/baby-piglet.jpg/CKnjvYEBIAIgBygCKAc/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0', 'desc': 'Shared with Dropbox', 'title': '1 photo'}
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=image_info):
            converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" target="_blank" title="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5">https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" target="_blank" title="1 photo"><img src="https://photos-6.dropbox.com/t/2/AAAlawaeD61TyNewO5vVi-DGf2ZeuayfyHFdNTNzpGq-QA/12/271544745/jpeg/1024x1024/2/_/0/5/baby-piglet.jpg/CKnjvYEBIAIgBygCKAc/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0"></a></div>')

    def test_inline_dropbox_negative(self) -> None:
        # Make sure we're not overzealous in our conversion:
        msg = 'Look at the new dropbox logo: https://www.dropbox.com/static/images/home_logo.png'
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=None):
            converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at the new dropbox logo: <a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png">https://www.dropbox.com/static/images/home_logo.png</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fwww.dropbox.com%2Fstatic%2Fimages%2Fhome_logo.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fwww.dropbox.com%2Fstatic%2Fimages%2Fhome_logo.png&amp;size=thumbnail"></a></div>')

    def test_inline_dropbox_bad(self) -> None:
        # Don't fail on bad dropbox links
        msg = "https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM"
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=None):
            converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p><a href="https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM" target="_blank" title="https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM">https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM</a></p>')

    def test_inline_github_preview(self) -> None:
        # Test photo album previews
        msg = 'Test: https://github.com/zulip/zulip/blob/master/static/images/logo/zulip-icon-128x128.png'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Test: <a href="https://github.com/zulip/zulip/blob/master/static/images/logo/zulip-icon-128x128.png" target="_blank" title="https://github.com/zulip/zulip/blob/master/static/images/logo/zulip-icon-128x128.png">https://github.com/zulip/zulip/blob/master/static/images/logo/zulip-icon-128x128.png</a></p>\n<div class="message_inline_image"><a href="https://github.com/zulip/zulip/blob/master/static/images/logo/zulip-icon-128x128.png" target="_blank" title="https://github.com/zulip/zulip/blob/master/static/images/logo/zulip-icon-128x128.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fraw.githubusercontent.com%2Fzulip%2Fzulip%2Fmaster%2Fstatic%2Fimages%2Flogo%2Fzulip-icon-128x128.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fraw.githubusercontent.com%2Fzulip%2Fzulip%2Fmaster%2Fstatic%2Fimages%2Flogo%2Fzulip-icon-128x128.png&amp;size=thumbnail"></a></div>')

        msg = 'Test: https://developer.github.com/assets/images/hero-circuit-bg.png'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Test: <a href="https://developer.github.com/assets/images/hero-circuit-bg.png" target="_blank" title="https://developer.github.com/assets/images/hero-circuit-bg.png">https://developer.github.com/assets/images/hero-circuit-bg.png</a></p>\n<div class="message_inline_image"><a href="https://developer.github.com/assets/images/hero-circuit-bg.png" target="_blank" title="https://developer.github.com/assets/images/hero-circuit-bg.png"><img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fdeveloper.github.com%2Fassets%2Fimages%2Fhero-circuit-bg.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fdeveloper.github.com%2Fassets%2Fimages%2Fhero-circuit-bg.png&amp;size=thumbnail"></a></div>')

    def test_twitter_id_extraction(self) -> None:
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/#!/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/statuses/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858/'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/photo/1'), '410766290349879296')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/'), '410766290349879296')

    def test_inline_interesting_links(self) -> None:
        def make_link(url: str) -> str:
            return '<a href="%s" target="_blank" title="%s">%s</a>' % (url, url, url)

        normal_tweet_html = ('<a href="https://twitter.com/Twitter" target="_blank"'
                             ' title="https://twitter.com/Twitter">@Twitter</a> '
                             'meets @seepicturely at #tcdisrupt cc.'
                             '<a href="https://twitter.com/boscomonkey" target="_blank"'
                             ' title="https://twitter.com/boscomonkey">@boscomonkey</a> '
                             '<a href="https://twitter.com/episod" target="_blank"'
                             ' title="https://twitter.com/episod">@episod</a> '
                             '<a href="http://t.co/6J2EgYM" target="_blank"'
                             ' title="http://t.co/6J2EgYM">http://instagr.am/p/MuW67/</a>')

        mention_in_link_tweet_html = """<a href="http://t.co/@foo" target="_blank" title="http://t.co/@foo">http://foo.com</a>"""

        media_tweet_html = ('<a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3">'
                            'http://twitter.com/NEVNBoston/status/421654515616849920/photo/1</a>')

        emoji_in_tweet_html = """Zulip is <span aria-label=\"100\" class="emoji emoji-1f4af" role=\"img\" title="100">:100:</span>% open-source!"""

        def make_inline_twitter_preview(url: str, tweet_html: str, image_html: str='') -> str:
            ## As of right now, all previews are mocked to be the exact same tweet
            return ('<div class="inline-preview-twitter">'
                    '<div class="twitter-tweet">'
                    '<a href="%s" target="_blank">'
                    '<img class="twitter-avatar"'
                    ' src="https://external-content.zulipcdn.net/external_content/1f7cd2436976d410eab8189ebceda87ae0b34ead/687474703a2f2f7062732e7477696d672e63'
                    '6f6d2f70726f66696c655f696d616765732f313338303931323137332f53637265656e5f73686f745f323031312d30362d30335f61745f372e33352e33'
                    '365f504d5f6e6f726d616c2e706e67">'
                    '</a>'
                    '<p>%s</p>'
                    '<span>- Eoin McMillan (@imeoin)</span>'
                    '%s'
                    '</div>'
                    '</div>') % (url, tweet_html, image_html)

        msg = 'http://www.twitter.com'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com'))

        msg = 'http://www.twitter.com/wdaher/'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/'))

        msg = 'http://www.twitter.com/wdaher/status/3'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/status/3'))

        # id too long
        msg = 'http://www.twitter.com/wdaher/status/2879779692873154569'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/status/2879779692873154569'))

        # id too large (i.e. tweet doesn't exist)
        msg = 'http://www.twitter.com/wdaher/status/999999999999999999'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/status/999999999999999999'))

        msg = 'http://www.twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (
            make_link('http://www.twitter.com/wdaher/status/287977969287315456'),
            make_inline_twitter_preview('http://www.twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        msg = 'https://www.twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (
            make_link('https://www.twitter.com/wdaher/status/287977969287315456'),
            make_inline_twitter_preview('https://www.twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        msg = 'http://twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (
            make_link('http://twitter.com/wdaher/status/287977969287315456'),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        # A max of 3 will be converted
        msg = ('http://twitter.com/wdaher/status/287977969287315456 '
               'http://twitter.com/wdaher/status/287977969287315457 '
               'http://twitter.com/wdaher/status/287977969287315457 '
               'http://twitter.com/wdaher/status/287977969287315457')
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s %s %s %s</p>\n%s%s%s' % (
            make_link('http://twitter.com/wdaher/status/287977969287315456'),
            make_link('http://twitter.com/wdaher/status/287977969287315457'),
            make_link('http://twitter.com/wdaher/status/287977969287315457'),
            make_link('http://twitter.com/wdaher/status/287977969287315457'),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456', normal_tweet_html),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315457', normal_tweet_html),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315457', normal_tweet_html)))

        # Tweet has a mention in a URL, only the URL is linked
        msg = 'http://twitter.com/wdaher/status/287977969287315458'

        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (
            make_link('http://twitter.com/wdaher/status/287977969287315458'),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315458', mention_in_link_tweet_html)))

        # Tweet with an image
        msg = 'http://twitter.com/wdaher/status/287977969287315459'

        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (
            make_link('http://twitter.com/wdaher/status/287977969287315459'),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315459',
                                        media_tweet_html,
                                        ('<div class="twitter-image">'
                                         '<a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3">'
                                         '<img src="https://pbs.twimg.com/media/BdoEjD4IEAIq86Z.jpg:small">'
                                         '</a>'
                                         '</div>'))))

        msg = 'http://twitter.com/wdaher/status/287977969287315460'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (
            make_link('http://twitter.com/wdaher/status/287977969287315460'),
            make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315460', emoji_in_tweet_html)))

    def test_fetch_tweet_data_settings_validation(self) -> None:
        with self.settings(TEST_SUITE=False, TWITTER_CONSUMER_KEY=None):
            self.assertIs(None, bugdown.fetch_tweet_data('287977969287315459'))

    def test_content_has_emoji(self) -> None:
        self.assertFalse(bugdown.content_has_emoji_syntax('boring'))
        self.assertFalse(bugdown.content_has_emoji_syntax('hello: world'))
        self.assertFalse(bugdown.content_has_emoji_syntax(':foobar'))
        self.assertFalse(bugdown.content_has_emoji_syntax('::: hello :::'))

        self.assertTrue(bugdown.content_has_emoji_syntax('foo :whatever:'))
        self.assertTrue(bugdown.content_has_emoji_syntax('\n:whatever:'))
        self.assertTrue(bugdown.content_has_emoji_syntax(':smile: ::::::'))

    def test_realm_emoji(self) -> None:
        def emoji_img(name: str, file_name: str, realm_id: int) -> str:
            return '<img alt="%s" class="emoji" src="%s" title="%s">' % (
                name, get_emoji_url(file_name, realm_id), name[1:-1].replace("_", " "))

        realm = get_realm('zulip')

        # Needs to mock an actual message because that's how bugdown obtains the realm
        msg = Message(sender=self.example_user('hamlet'))
        converted = bugdown.convert(":green_tick:", message_realm=realm, message=msg)
        realm_emoji = RealmEmoji.objects.filter(realm=realm,
                                                name='green_tick',
                                                deactivated=False).get()
        self.assertEqual(converted, '<p>%s</p>' % (emoji_img(':green_tick:', realm_emoji.file_name, realm.id)))

        # Deactivate realm emoji.
        do_remove_realm_emoji(realm, 'green_tick')
        converted = bugdown.convert(":green_tick:", message_realm=realm, message=msg)
        self.assertEqual(converted, '<p>:green_tick:</p>')

    def test_deactivated_realm_emoji(self) -> None:
        # Deactivate realm emoji.
        realm = get_realm('zulip')
        do_remove_realm_emoji(realm, 'green_tick')

        msg = Message(sender=self.example_user('hamlet'))
        converted = bugdown.convert(":green_tick:", message_realm=realm, message=msg)
        self.assertEqual(converted, '<p>:green_tick:</p>')

    def test_unicode_emoji(self) -> None:
        msg = u'\u2615'  # ☕
        converted = bugdown_convert(msg)
        self.assertEqual(converted, u'<p><span aria-label=\"coffee\" class="emoji emoji-2615" role=\"img\" title="coffee">:coffee:</span></p>')

        msg = u'\u2615\u2615'  # ☕☕
        converted = bugdown_convert(msg)
        self.assertEqual(converted, u'<p><span aria-label=\"coffee\" class="emoji emoji-2615" role=\"img\" title="coffee">:coffee:</span><span aria-label=\"coffee\" class="emoji emoji-2615" role=\"img\" title="coffee">:coffee:</span></p>')

    def test_no_translate_emoticons_if_off(self) -> None:
        user_profile = self.example_user('othello')
        do_set_user_display_setting(user_profile, 'translate_emoticons', False)
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = u':)'
        expected = u'<p>:)</p>'
        converted = render_markdown(msg, content)
        self.assertEqual(converted, expected)

    def test_same_markup(self) -> None:
        msg = u'\u2615'  # ☕
        unicode_converted = bugdown_convert(msg)

        msg = u':coffee:'  # ☕☕
        converted = bugdown_convert(msg)
        self.assertEqual(converted, unicode_converted)

    def test_realm_patterns(self) -> None:
        realm = get_realm('zulip')
        url_format_string = r"https://trac.zulip.net/ticket/%(id)s"
        realm_filter = RealmFilter(realm=realm,
                                   pattern=r"#(?P<id>[0-9]{2,8})",
                                   url_format_string=url_format_string)
        realm_filter.save()
        self.assertEqual(
            realm_filter.__str__(),
            '<RealmFilter(zulip): #(?P<id>[0-9]{2,8})'
            ' https://trac.zulip.net/ticket/%(id)s>')

        msg = Message(sender=self.example_user('othello'))
        msg.set_topic_name("#444")

        flush_per_request_caches()

        content = "We should fix #224 and #115, but not issue#124 or #1124z or [trac #15](https://trac.zulip.net/ticket/16) today."
        converted = bugdown.convert(content, message_realm=realm, message=msg)
        converted_topic = bugdown.topic_links(realm.id, msg.topic_name())

        self.assertEqual(converted, '<p>We should fix <a href="https://trac.zulip.net/ticket/224" target="_blank" title="https://trac.zulip.net/ticket/224">#224</a> and <a href="https://trac.zulip.net/ticket/115" target="_blank" title="https://trac.zulip.net/ticket/115">#115</a>, but not issue#124 or #1124z or <a href="https://trac.zulip.net/ticket/16" target="_blank" title="https://trac.zulip.net/ticket/16">trac #15</a> today.</p>')
        self.assertEqual(converted_topic, [u'https://trac.zulip.net/ticket/444'])

        RealmFilter(realm=realm, pattern=r'#(?P<id>[a-zA-Z]+-[0-9]+)',
                    url_format_string=r'https://trac.zulip.net/ticket/%(id)s').save()
        msg = Message(sender=self.example_user('hamlet'))

        content = '#ZUL-123 was fixed and code was deployed to production, also #zul-321 was deployed to staging'
        converted = bugdown.convert(content, message_realm=realm, message=msg)

        self.assertEqual(converted, '<p><a href="https://trac.zulip.net/ticket/ZUL-123" target="_blank" title="https://trac.zulip.net/ticket/ZUL-123">#ZUL-123</a> was fixed and code was deployed to production, also <a href="https://trac.zulip.net/ticket/zul-321" target="_blank" title="https://trac.zulip.net/ticket/zul-321">#zul-321</a> was deployed to staging</p>')

        def was_converted(content: str) -> bool:
            converted = bugdown.convert(content, message_realm=realm, message=msg)
            return 'trac.zulip.net' in converted

        self.assertTrue(was_converted('Hello #123 World'))
        self.assertTrue(not was_converted('Hello #123World'))
        self.assertTrue(not was_converted('Hello#123 World'))
        self.assertTrue(not was_converted('Hello#123World'))
        self.assertTrue(was_converted('チケットは#123です'))
        self.assertTrue(was_converted('チケットは #123です'))
        self.assertTrue(was_converted('チケットは#123 です'))
        self.assertTrue(was_converted('チケットは #123 です'))
        self.assertTrue(was_converted('(#123)'))
        self.assertTrue(was_converted('#123>'))
        self.assertTrue(was_converted('"#123"'))
        self.assertTrue(was_converted('#123@'))
        self.assertTrue(not was_converted(')#123('))
        self.assertTrue(not was_converted('##123'))

    def test_maybe_update_markdown_engines(self) -> None:
        realm = get_realm('zulip')
        url_format_string = r"https://trac.zulip.net/ticket/%(id)s"
        realm_filter = RealmFilter(realm=realm,
                                   pattern=r"#(?P<id>[0-9]{2,8})",
                                   url_format_string=url_format_string)
        realm_filter.save()

        bugdown.realm_filter_data = {}
        bugdown.maybe_update_markdown_engines(None, False)
        all_filters = bugdown.realm_filter_data
        zulip_filters = all_filters[realm.id]
        self.assertEqual(len(zulip_filters), 1)
        self.assertEqual(zulip_filters[0],
                         (u'#(?P<id>[0-9]{2,8})', u'https://trac.zulip.net/ticket/%(id)s', realm_filter.id))

    def test_flush_realm_filter(self) -> None:
        realm = get_realm('zulip')

        def flush() -> None:
            '''
            flush_realm_filter is a post-save hook, so calling it
            directly for testing is kind of awkward
            '''
            class Instance:
                realm_id = None  # type: Optional[int]
            instance = Instance()
            instance.realm_id = realm.id
            flush_realm_filter(sender=None, instance=instance)

        def save_new_realm_filter() -> None:
            realm_filter = RealmFilter(realm=realm,
                                       pattern=r"whatever",
                                       url_format_string='whatever')
            realm_filter.save()

        # start fresh for our realm
        flush()
        self.assertFalse(realm_in_local_realm_filters_cache(realm.id))

        # call this just for side effects of populating the cache
        realm_filters_for_realm(realm.id)
        self.assertTrue(realm_in_local_realm_filters_cache(realm.id))

        # Saving a new RealmFilter should have the side effect of
        # flushing the cache.
        save_new_realm_filter()
        self.assertFalse(realm_in_local_realm_filters_cache(realm.id))

        # and flush it one more time, to make sure we don't get a KeyError
        flush()
        self.assertFalse(realm_in_local_realm_filters_cache(realm.id))

    def test_realm_patterns_negative(self) -> None:
        realm = get_realm('zulip')
        RealmFilter(realm=realm, pattern=r"#(?P<id>[0-9]{2,8})",
                    url_format_string=r"https://trac.zulip.net/ticket/%(id)s").save()
        boring_msg = Message(sender=self.example_user('othello'))
        boring_msg.set_topic_name("no match here")
        converted_boring_topic = bugdown.topic_links(realm.id, boring_msg.topic_name())
        self.assertEqual(converted_boring_topic, [])

    def test_is_status_message(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = '/me makes a list\n* one\n* two'
        rendered_content = render_markdown(msg, content)
        self.assertEqual(
            rendered_content,
            '<p>/me makes a list</p>\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>'
        )
        self.assertFalse(Message.is_status_message(content, rendered_content))

        content = '/me takes a walk'
        rendered_content = render_markdown(msg, content)
        self.assertEqual(
            rendered_content,
            '<p>/me takes a walk</p>'
        )
        self.assertTrue(Message.is_status_message(content, rendered_content))

        content = '/me writes a second line\nline'
        rendered_content = render_markdown(msg, content)
        self.assertEqual(
            rendered_content,
            '<p>/me writes a second line<br>\nline</p>'
        )
        self.assertFalse(Message.is_status_message(content, rendered_content))

    def test_alert_words(self) -> None:
        user_profile = self.example_user('othello')
        do_set_alert_words(user_profile, ["ALERTWORD", "scaryword"])
        msg = Message(sender=user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids={user_profile.id})

        content = "We have an ALERTWORD day today!"
        self.assertEqual(render(msg, content), "<p>We have an ALERTWORD day today!</p>")
        self.assertEqual(msg.user_ids_with_alert_words, set([user_profile.id]))

        msg = Message(sender=user_profile, sending_client=get_client("test"))
        content = "We have a NOTHINGWORD day today!"
        self.assertEqual(render(msg, content), "<p>We have a NOTHINGWORD day today!</p>")
        self.assertEqual(msg.user_ids_with_alert_words, set())

    def test_alert_words_returns_user_ids_with_alert_words(self) -> None:
        alert_words_for_users = {
            'hamlet': ['how'], 'cordelia': ['this possible'],
            'iago': ['hello'], 'prospero': ['hello'],
            'othello': ['how are you'], 'aaron': ['hey']
        }  # type: Dict[str, List[str]]
        user_profiles = {}  # type: Dict[str, UserProfile]
        user_ids = set()  # type: Set[int]
        for (username, alert_words) in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            user_ids.add(user_profile.id)
            do_set_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user('polonius')
        user_ids.add(sender_user_profile.id)
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids = user_ids)

        content = "hello how is this possible how are you doing today"
        render(msg, content)
        expected_user_ids = {
            user_profiles['hamlet'].id, user_profiles['cordelia'].id, user_profiles['iago'].id,
            user_profiles['prospero'].id, user_profiles['othello'].id
        }  # type: Set[int]
        # All users except aaron have their alert word appear in the message content
        self.assertEqual(msg.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_user_ids_with_alert_words_1(self) -> None:
        alert_words_for_users = {
            'hamlet': ['provisioning', 'Prod deployment'],
            'cordelia': ['test', 'Prod'],
            'iago': ['prod'], 'prospero': ['deployment'],
            'othello': ['last']
        }  # type: Dict[str, List[str]]
        user_profiles = {}  # type: Dict[str, UserProfile]
        user_ids = set()  # type: Set[int]
        for (username, alert_words) in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            user_ids.add(user_profile.id)
            do_set_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user('polonius')
        user_ids.add(sender_user_profile.id)
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids = user_ids)

        content = """Hello, everyone. Prod deployment has been completed
        And this is a new line
        to test out how markdown convert this into something line ending splitted array
        and this is a new line
        last"""
        render(msg, content)
        expected_user_ids = {
            user_profiles['hamlet'].id,
            user_profiles['cordelia'].id,
            user_profiles['iago'].id,
            user_profiles['prospero'].id,
            user_profiles['othello'].id
        }  # type: Set[int]
        # All users have their alert word appear in the message content
        self.assertEqual(msg.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_user_ids_with_alert_words_in_french(self) -> None:
        alert_words_for_users = {
            'hamlet': ['réglementaire', 'une politique', 'une merveille'],
            'cordelia': ['énormément', 'Prod'],
            'iago': ['prod'], 'prospero': ['deployment'],
            'othello': ['last']
        }  # type: Dict[str, List[str]]
        user_profiles = {}  # type: Dict[str, UserProfile]
        user_ids = set()  # type: Set[int]
        for (username, alert_words) in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            user_ids.add(user_profile.id)
            do_set_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user('polonius')
        user_ids.add(sender_user_profile.id)
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids = user_ids)

        content = """This is to test out alert words work in languages with accented characters too
        bonjour est (énormément) ce a quoi ressemble le français
        et j'espère qu'il n'y n' réglementaire a pas de mots d'alerte dans ce texte français
        """
        render(msg, content)
        expected_user_ids = {user_profiles['hamlet'].id, user_profiles['cordelia'].id}  # type: Set[int]
        # Only hamlet and cordelia have their alert-words appear in the message content
        self.assertEqual(msg.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_returns_empty_user_ids_with_alert_words(self) -> None:
        alert_words_for_users = {
            'hamlet': [], 'cordelia': [], 'iago': [], 'prospero': [],
            'othello': [], 'aaron': []
        }  # type: Dict[str, List[str]]
        user_profiles = {}  # type: Dict[str, UserProfile]
        user_ids = set()  # type: Set[int]
        for (username, alert_words) in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_set_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user('polonius')
        msg = Message(sender=user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids = user_ids)

        content = """hello how is this possible how are you doing today
        This is to test that the no user_ids who have alrert wourldword is participating
        in sending of the message
        """
        render(msg, content)
        expected_user_ids = set()  # type: Set[int]
        # None of the users have their alert-words appear in the message content
        self.assertEqual(msg.user_ids_with_alert_words, expected_user_ids)

    def get_mock_alert_words(self, num_words: int, word_length: int) -> List[str]:
        alert_words = ['x' * word_length] * num_words  # type List[str]
        return alert_words

    def test_alert_words_with_empty_alert_words(self) -> None:
        alert_words_for_users = {
            'hamlet': [],
            'cordelia': [],
            'iago': [],
            'othello': []
        }  # type: Dict[str, List[str]]
        user_profiles = {}  # type: Dict[str, UserProfile]
        user_ids = set()  # type: Set[int]
        for (username, alert_words) in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_set_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user('polonius')
        user_ids = {user_profiles['hamlet'].id, user_profiles['iago'].id, user_profiles['othello'].id}
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids = user_ids)

        content = """This is to test a empty alert words i.e. no user has any alert-words set"""
        render(msg, content)
        expected_user_ids = set()  # type: Set[int]
        self.assertEqual(msg.user_ids_with_alert_words, expected_user_ids)

    def test_alert_words_retuns_user_ids_with_alert_words_with_huge_alert_words(self) -> None:

        alert_words_for_users = {
            'hamlet': ['issue124'],
            'cordelia': self.get_mock_alert_words(500, 10),
            'iago': self.get_mock_alert_words(500, 10),
            'othello': self.get_mock_alert_words(500, 10)
        }  # type: Dict[str, List[str]]
        user_profiles = {}  # type: Dict[str, UserProfile]
        user_ids = set()  # type: Set[int]
        for (username, alert_words) in alert_words_for_users.items():
            user_profile = self.example_user(username)
            user_profiles.update({username: user_profile})
            do_set_alert_words(user_profile, alert_words)
        sender_user_profile = self.example_user('polonius')
        user_ids = {user_profiles['hamlet'].id, user_profiles['iago'].id, user_profiles['othello'].id}
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm_alert_words_automaton = get_alert_word_automaton(sender_user_profile.realm)

        def render(msg: Message, content: str) -> str:
            return render_markdown(msg,
                                   content,
                                   realm_alert_words_automaton=realm_alert_words_automaton,
                                   user_ids = user_ids)

        content = """The code above will print 10 random values of numbers between 1 and 100.
        The second line, for x in range(10), determines how many values will be printed (when you use
        range(x), the number that you use in place of x will be the amount of values that you'll have
        printed. if you want 20 values, use range(20). use range(5) if you only want 5 values returned,
        etc.). I was talking abou the issue124 on github. Then the third line: print random.randint(1,101) will automatically select a random integer
        between 1 and 100 for you. The process is fairly simple
        """
        render(msg, content)
        expected_user_ids = {user_profiles['hamlet'].id}  # type: Set[int]
        # Only hamlet has alert-word 'issue124' present in the message content
        self.assertEqual(msg.user_ids_with_alert_words, expected_user_ids)

    def test_mention_wildcard(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@**all** test"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" data-user-id="*">'
                         '@all'
                         '</span> test</p>')
        self.assertTrue(msg.mentions_wildcard)

    def test_mention_everyone(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@**everyone** test"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" data-user-id="*">'
                         '@everyone'
                         '</span> test</p>')
        self.assertTrue(msg.mentions_wildcard)

    def test_mention_stream(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@**stream** test"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" data-user-id="*">'
                         '@stream'
                         '</span> test</p>')
        self.assertTrue(msg.mentions_wildcard)

    def test_mention_at_wildcard(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@all test"
        self.assertEqual(render_markdown(msg, content),
                         '<p>@all test</p>')
        self.assertFalse(msg.mentions_wildcard)
        self.assertEqual(msg.mentions_user_ids, set([]))

    def test_mention_at_everyone(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@everyone test"
        self.assertEqual(render_markdown(msg, content),
                         '<p>@everyone test</p>')
        self.assertFalse(msg.mentions_wildcard)
        self.assertEqual(msg.mentions_user_ids, set([]))

    def test_mention_word_starting_with_at_wildcard(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "test @alleycat.com test"
        self.assertEqual(render_markdown(msg, content),
                         '<p>test @alleycat.com test</p>')
        self.assertFalse(msg.mentions_wildcard)
        self.assertEqual(msg.mentions_user_ids, set([]))

    def test_mention_at_normal_user(self) -> None:
        user_profile = self.example_user('othello')
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@aaron test"
        self.assertEqual(render_markdown(msg, content),
                         '<p>@aaron test</p>')
        self.assertFalse(msg.mentions_wildcard)
        self.assertEqual(msg.mentions_user_ids, set([]))

    def test_mention_single(self) -> None:
        sender_user_profile = self.example_user('othello')
        user_profile = self.example_user('hamlet')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        user_id = user_profile.id

        content = "@**King Hamlet**"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" '
                         'data-user-id="%s">'
                         '@King Hamlet</span></p>' % (user_id))
        self.assertEqual(msg.mentions_user_ids, set([user_profile.id]))

    def test_mention_silent(self) -> None:
        sender_user_profile = self.example_user('othello')
        user_profile = self.example_user('hamlet')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        user_id = user_profile.id

        content = "@_**King Hamlet**"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention silent" '
                         'data-user-id="%s">'
                         'King Hamlet</span></p>' % (user_id))
        self.assertEqual(msg.mentions_user_ids, set())

    def test_possible_mentions(self) -> None:
        def assert_mentions(content: str, names: Set[str]) -> None:
            self.assertEqual(possible_mentions(content), names)

        assert_mentions('', set())
        assert_mentions('boring', set())
        assert_mentions('@**all**', set())
        assert_mentions('smush@**steve**smush', set())

        assert_mentions(
            'Hello @**King Hamlet** and @**Cordelia Lear**\n@**Foo van Barson|1234** @**all**',
            {'King Hamlet', 'Cordelia Lear', 'Foo van Barson|1234'}
        )

    def test_mention_multiple(self) -> None:
        sender_user_profile = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "@**King Hamlet** and @**Cordelia Lear**, check this out"

        self.assertEqual(render_markdown(msg, content),
                         '<p>'
                         '<span class="user-mention" '
                         'data-user-id="%s">@King Hamlet</span> and '
                         '<span class="user-mention" '
                         'data-user-id="%s">@Cordelia Lear</span>, '
                         'check this out</p>' % (hamlet.id, cordelia.id))
        self.assertEqual(msg.mentions_user_ids, set([hamlet.id, cordelia.id]))

    def test_mention_in_quotes(self) -> None:
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        msg = Message(sender=othello, sending_client=get_client("test"))

        content = "> @**King Hamlet** and @**Othello, the Moor of Venice**\n\n @**King Hamlet** and @**Cordelia Lear**"
        self.assertEqual(render_markdown(msg, content),
                         '<blockquote>\n<p>'
                         '<span class="user-mention silent" data-user-id="%s">King Hamlet</span>'
                         ' and '
                         '<span class="user-mention silent" data-user-id="%s">Othello, the Moor of Venice</span>'
                         '</p>\n</blockquote>\n'
                         '<p>'
                         '<span class="user-mention" data-user-id="%s">@King Hamlet</span>'
                         ' and '
                         '<span class="user-mention" data-user-id="%s">@Cordelia Lear</span>'
                         '</p>' % (hamlet.id, othello.id, hamlet.id, cordelia.id))
        self.assertEqual(msg.mentions_user_ids, set([hamlet.id, cordelia.id]))

        # Both fenced quote and > quote should be identical for both silent and regular syntax.
        expected = ('<blockquote>\n<p>'
                    '<span class="user-mention silent" data-user-id="%s">King Hamlet</span>'
                    '</p>\n</blockquote>' % (hamlet.id))
        content = "```quote\n@**King Hamlet**\n```"
        self.assertEqual(render_markdown(msg, content), expected)
        self.assertEqual(msg.mentions_user_ids, set())
        content = "> @**King Hamlet**"
        self.assertEqual(render_markdown(msg, content), expected)
        self.assertEqual(msg.mentions_user_ids, set())
        content = "```quote\n@_**King Hamlet**\n```"
        self.assertEqual(render_markdown(msg, content), expected)
        self.assertEqual(msg.mentions_user_ids, set())
        content = "> @_**King Hamlet**"
        self.assertEqual(render_markdown(msg, content), expected)
        self.assertEqual(msg.mentions_user_ids, set())

    def test_mention_duplicate_full_name(self) -> None:
        realm = get_realm('zulip')

        def make_user(email: str, full_name: str) -> UserProfile:
            return create_user(
                email=email,
                password='whatever',
                realm=realm,
                full_name=full_name,
                short_name='whatever',
            )

        sender_user_profile = self.example_user('othello')
        twin1 = make_user('twin1@example.com', 'Mark Twin')
        twin2 = make_user('twin2@example.com', 'Mark Twin')
        cordelia = self.example_user('cordelia')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "@**Mark Twin|{}**, @**Mark Twin|{}** and @**Cordelia Lear**, hi.".format(twin1.id, twin2.id)

        self.assertEqual(render_markdown(msg, content),
                         '<p>'
                         '<span class="user-mention" '
                         'data-user-id="%s">@Mark Twin</span>, '
                         '<span class="user-mention" '
                         'data-user-id="%s">@Mark Twin</span> and '
                         '<span class="user-mention" '
                         'data-user-id="%s">@Cordelia Lear</span>, '
                         'hi.</p>' % (twin1.id, twin2.id, cordelia.id))
        self.assertEqual(msg.mentions_user_ids, set([twin1.id, twin2.id, cordelia.id]))

    def test_mention_invalid(self) -> None:
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "Hey @**Nonexistent User**"
        self.assertEqual(render_markdown(msg, content),
                         '<p>Hey @<strong>Nonexistent User</strong></p>')
        self.assertEqual(msg.mentions_user_ids, set())

    def create_user_group_for_test(self, user_group_name: str) -> UserGroup:
        othello = self.example_user('othello')
        return create_user_group(user_group_name, [othello], get_realm('zulip'))

    def test_user_group_mention_single(self) -> None:
        sender_user_profile = self.example_user('othello')
        user_profile = self.example_user('hamlet')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        user_id = user_profile.id
        user_group = self.create_user_group_for_test('support')

        content = "@**King Hamlet** @*support*"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" '
                         'data-user-id="%s">'
                         '@King Hamlet</span> '
                         '<span class="user-group-mention" '
                         'data-user-group-id="%s">'
                         '@support</span></p>' % (user_id,
                                                  user_group.id))
        self.assertEqual(msg.mentions_user_ids, set([user_profile.id]))
        self.assertEqual(msg.mentions_user_group_ids, set([user_group.id]))

    def test_possible_user_group_mentions(self) -> None:
        def assert_mentions(content: str, names: Set[str]) -> None:
            self.assertEqual(possible_user_group_mentions(content), names)

        assert_mentions('', set())
        assert_mentions('boring', set())
        assert_mentions('@**all**', set())
        assert_mentions('smush@*steve*smush', set())

        assert_mentions(
            '@*support* Hello @**King Hamlet** and @**Cordelia Lear**\n'
            '@**Foo van Barson** @**all**', {'support'}
        )

        assert_mentions(
            'Attention @*support*, @*frontend* and @*backend*\ngroups.',
            {'support', 'frontend', 'backend'}
        )

    def test_user_group_mention_multiple(self) -> None:
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        support = self.create_user_group_for_test('support')
        backend = self.create_user_group_for_test('backend')

        content = "@*support* and @*backend*, check this out"
        self.assertEqual(render_markdown(msg, content),
                         '<p>'
                         '<span class="user-group-mention" '
                         'data-user-group-id="%s">'
                         '@support</span> '
                         'and '
                         '<span class="user-group-mention" '
                         'data-user-group-id="%s">'
                         '@backend</span>, '
                         'check this out'
                         '</p>' % (support.id, backend.id))

        self.assertEqual(msg.mentions_user_group_ids, set([support.id, backend.id]))

    def test_user_group_mention_invalid(self) -> None:
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "Hey @*Nonexistent group*"
        self.assertEqual(render_markdown(msg, content),
                         '<p>Hey @<em>Nonexistent group</em></p>')
        self.assertEqual(msg.mentions_user_group_ids, set())

    def test_stream_single(self) -> None:
        denmark = get_stream('Denmark', get_realm('zulip'))
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = "#**Denmark**"
        self.assertEqual(
            render_markdown(msg, content),
            '<p><a class="stream" data-stream-id="{d.id}" href="/#narrow/stream/{d.id}-Denmark">#{d.name}</a></p>'.format(
                d=denmark
            ))

    def test_stream_multiple(self) -> None:
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm = get_realm('zulip')
        denmark = get_stream('Denmark', realm)
        scotland = get_stream('Scotland', realm)
        content = "Look to #**Denmark** and #**Scotland**, there something"
        self.assertEqual(render_markdown(msg, content),
                         '<p>Look to '
                         '<a class="stream" '
                         'data-stream-id="{denmark.id}" '
                         'href="/#narrow/stream/{denmark.id}-Denmark">#{denmark.name}</a> and '
                         '<a class="stream" '
                         'data-stream-id="{scotland.id}" '
                         'href="/#narrow/stream/{scotland.id}-Scotland">#{scotland.name}</a>, '
                         'there something</p>'.format(denmark=denmark, scotland=scotland))

    def test_stream_case_sensitivity(self) -> None:
        realm = get_realm('zulip')
        case_sens = Stream.objects.create(name='CaseSens', realm=realm)
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = "#**CaseSens**"
        self.assertEqual(
            render_markdown(msg, content),
            '<p><a class="stream" data-stream-id="{s.id}" href="/#narrow/stream/{s.id}-{s.name}">#{s.name}</a></p>'.format(
                s=case_sens
            ))

    def test_stream_case_sensitivity_nonmatching(self) -> None:
        """#StreamName requires the stream be spelled with the correct case
        currently.  If we change that in the future, we'll need to change this
        test."""
        realm = get_realm('zulip')
        Stream.objects.create(name='CaseSens', realm=realm)
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = "#**casesens**"
        self.assertEqual(
            render_markdown(msg, content),
            '<p>#<strong>casesens</strong></p>')

    def test_possible_stream_names(self) -> None:
        content = '''#**test here**
            This mentions #**Denmark** too.
            #**garçon** #**천국** @**Ignore Person**
        '''
        self.assertEqual(
            bugdown.possible_linked_stream_names(content),
            {'test here', 'Denmark', 'garçon', '천국'}
        )

    def test_stream_unicode(self) -> None:
        realm = get_realm('zulip')
        uni = Stream.objects.create(name=u'привет', realm=realm)
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = u"#**привет**"
        quoted_name = '.D0.BF.D1.80.D0.B8.D0.B2.D0.B5.D1.82'
        href = '/#narrow/stream/{stream_id}-{quoted_name}'.format(
            stream_id=uni.id,
            quoted_name=quoted_name)
        self.assertEqual(
            render_markdown(msg, content),
            u'<p><a class="stream" data-stream-id="{s.id}" href="{href}">#{s.name}</a></p>'.format(
                s=uni,
                href=href,
            ))

    def test_stream_invalid(self) -> None:
        sender_user_profile = self.example_user('othello')
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "There #**Nonexistentstream**"
        self.assertEqual(render_markdown(msg, content),
                         '<p>There #<strong>Nonexistentstream</strong></p>')
        self.assertEqual(msg.mentions_user_ids, set())

    def test_in_app_modal_link(self) -> None:
        msg = '!modal_link(#settings, Settings page)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<a href="#settings" title="#settings">Settings page</a>'
            '</p>'
        )

    def test_image_preview_title(self) -> None:
        msg = '[My favorite image](https://example.com/testimage.png)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<a href="https://example.com/testimage.png" target="_blank" title="https://example.com/testimage.png">My favorite image</a>'
            '</p>\n'
            '<div class="message_inline_image">'
            '<a href="https://example.com/testimage.png" target="_blank" title="My favorite image">'
            '<img data-src-fullsize="/thumbnail?url=https%3A%2F%2Fexample.com%2Ftestimage.png&amp;size=full" src="/thumbnail?url=https%3A%2F%2Fexample.com%2Ftestimage.png&amp;size=thumbnail">'
            '</a>'
            '</div>'
        )

    def test_mit_rendering(self) -> None:
        """Test the markdown configs for the MIT Zephyr mirroring system;
        verifies almost all inline patterns are disabled, but
        inline_interesting_links is still enabled"""
        msg = "**test**"
        realm = get_realm("zephyr")
        client = get_client("zephyr_mirror")
        message = Message(sending_client=client,
                          sender=self.mit_user("sipbtest"))
        converted = bugdown.convert(msg, message_realm=realm, message=message)
        self.assertEqual(
            converted,
            "<p>**test**</p>",
        )
        msg = "* test"
        converted = bugdown.convert(msg, message_realm=realm, message=message)
        self.assertEqual(
            converted,
            "<p>* test</p>",
        )
        msg = "https://lists.debian.org/debian-ctte/2014/02/msg00173.html"
        converted = bugdown.convert(msg, message_realm=realm, message=message)
        self.assertEqual(
            converted,
            '<p><a href="https://lists.debian.org/debian-ctte/2014/02/msg00173.html" target="_blank" title="https://lists.debian.org/debian-ctte/2014/02/msg00173.html">https://lists.debian.org/debian-ctte/2014/02/msg00173.html</a></p>',
        )

    def test_url_to_a(self) -> None:
        url = 'javascript://example.com/invalidURL'
        converted = bugdown.url_to_a(db_data=None, url=url, text=url)
        self.assertEqual(
            converted,
            'javascript://example.com/invalidURL',
        )

    def test_disabled_code_block_processor(self) -> None:
        msg = "Hello,\n\n" +  \
              "    I am writing this message to test something. I am writing this message to test something."
        converted = bugdown_convert(msg)
        expected_output = '<p>Hello,</p>\n' +   \
                          '<div class="codehilite"><pre><span></span>I am writing this message to test something. I am writing this message to test something.\n' +     \
                          '</pre></div>'
        self.assertEqual(converted, expected_output)

        realm = Realm.objects.create(string_id='code_block_processor_test')
        bugdown.maybe_update_markdown_engines(realm.id, True)
        converted = bugdown.convert(msg, message_realm=realm, email_gateway=True)
        expected_output = '<p>Hello,</p>\n' +     \
                          '<p>I am writing this message to test something. I am writing this message to test something.</p>'
        self.assertEqual(converted, expected_output)

    def test_normal_link(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        msg = "http://example.com/#settings/"

        self.assertEqual(
            bugdown.convert(msg, message_realm=realm, message=message),
            '<p><a href="http://example.com/#settings/" target="_blank" title="http://example.com/#settings/">http://example.com/#settings/</a></p>'
        )

    def test_relative_link(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        msg = "http://zulip.testserver/#narrow/stream/999-hello"

        self.assertEqual(
            bugdown.convert(msg, message_realm=realm, message=message),
            '<p><a href="#narrow/stream/999-hello" title="#narrow/stream/999-hello">http://zulip.testserver/#narrow/stream/999-hello</a></p>'
        )

    def test_relative_link_streams_page(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        msg = "http://zulip.testserver/#streams/all"

        self.assertEqual(
            bugdown.convert(msg, message_realm=realm, message=message),
            '<p><a href="#streams/all" target="_blank" title="#streams/all">http://zulip.testserver/#streams/all</a></p>'
        )

    def test_md_relative_link(self) -> None:
        realm = get_realm("zulip")
        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))
        msg = "[hello](http://zulip.testserver/#narrow/stream/999-hello)"

        self.assertEqual(
            bugdown.convert(msg, message_realm=realm, message=message),
            '<p><a href="#narrow/stream/999-hello" title="#narrow/stream/999-hello">hello</a></p>'
        )

class BugdownApiTests(ZulipTestCase):
    def test_render_message_api(self) -> None:
        content = 'That is a **bold** statement'
        result = self.api_post(
            self.example_email("othello"),
            '/api/v1/messages/render',
            dict(content=content)
        )
        self.assert_json_success(result)
        self.assertEqual(result.json()['rendered'],
                         u'<p>That is a <strong>bold</strong> statement</p>')

    def test_render_mention_stream_api(self) -> None:
        """Determines whether we're correctly passing the realm context"""
        content = 'This mentions #**Denmark** and @**King Hamlet**.'
        result = self.api_post(
            self.example_email("othello"),
            '/api/v1/messages/render',
            dict(content=content)
        )
        self.assert_json_success(result)
        user_id = self.example_user('hamlet').id
        stream_id = get_stream('Denmark', get_realm('zulip')).id
        self.assertEqual(result.json()['rendered'],
                         u'<p>This mentions <a class="stream" data-stream-id="%s" href="/#narrow/stream/%s-Denmark">#Denmark</a> and <span class="user-mention" data-user-id="%s">@King Hamlet</span>.</p>' % (stream_id, stream_id, user_id))

class BugdownErrorTests(ZulipTestCase):
    def test_bugdown_error_handling(self) -> None:
        with self.simulated_markdown_failure():
            with self.assertRaises(BugdownRenderingException):
                bugdown_convert('')

    def test_send_message_errors(self) -> None:

        message = 'whatever'
        with self.simulated_markdown_failure():
            # We don't use assertRaisesRegex because it seems to not
            # handle i18n properly here on some systems.
            with self.assertRaises(JsonableError):
                self.send_stream_message(self.example_email("othello"), "Denmark", message)

    def test_ultra_long_rendering(self) -> None:
        """A rendered message with an ultra-long lenght (> 10 * MAX_MESSAGE_LENGTH)
        throws an exception"""
        msg = u'mock rendered message\n' * MAX_MESSAGE_LENGTH

        with mock.patch('zerver.lib.bugdown.timeout', return_value=msg), \
                mock.patch('zerver.lib.bugdown.bugdown_logger'):
            with self.assertRaises(BugdownRenderingException):
                bugdown_convert(msg)


class BugdownAvatarTestCase(ZulipTestCase):
    def test_possible_avatar_emails(self) -> None:
        content = '''
            hello !avatar(foo@example.com) my email is ignore@ignore.com
            !gravatar(bar@yo.tv)

            smushing!avatar(hamlet@example.org) is allowed
        '''
        self.assertEqual(
            bugdown.possible_avatar_emails(content),
            {'foo@example.com', 'bar@yo.tv', 'hamlet@example.org'},
        )

    def test_avatar_with_id(self) -> None:
        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))

        user_profile = self.example_user('hamlet')
        msg = '!avatar({0})'.format(user_profile.email)
        converted = bugdown.convert(msg, message=message)
        values = {'email': user_profile.email, 'id': user_profile.id}
        self.assertEqual(
            converted,
            '<p><img alt="{email}" class="message_body_gravatar" src="/avatar/{id}?s=30" title="{email}"></p>'.format(**values))

    def test_avatar_of_unregistered_user(self) -> None:
        sender_user_profile = self.example_user('othello')
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))

        email = 'fakeuser@example.com'
        msg = '!avatar({0})'.format(email)
        converted = bugdown.convert(msg, message=message)
        self.assertEqual(
            converted,
            '<p><img alt="{0}" class="message_body_gravatar" src="/avatar/{0}?s=30" title="{0}"></p>'.format(email))
