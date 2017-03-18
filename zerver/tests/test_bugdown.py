# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase

from zerver.lib import bugdown
from zerver.lib.actions import (
    check_add_realm_emoji,
    do_remove_realm_emoji,
    do_set_alert_words,
    get_realm,
)
from zerver.lib.alert_words import alert_words_in_realm
from zerver.lib.camo import get_camo_url
from zerver.lib.message import render_markdown
from zerver.lib.request import (
    JsonableError,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.str_utils import force_str
from zerver.models import (
    realm_in_local_realm_filters_cache,
    flush_per_request_caches,
    flush_realm_filter,
    get_client,
    get_realm,
    get_user_profile_by_email,
    get_stream,
    realm_filters_for_realm,
    Message,
    Stream,
    Realm,
    RealmFilter,
    Recipient,
)

import mock
import os
import ujson
import six

from six.moves import urllib
from zerver.lib.str_utils import NonBinaryStr
from typing import Any, AnyStr, Dict, List, Optional, Tuple, Text

class FencedBlockPreprocessorTest(TestCase):
    def test_simple_quoting(self):
        # type: () -> None
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

    def test_serial_quoting(self):
        # type: () -> None
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

    def test_serial_code(self):
        # type: () -> None
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code # type: ignore # mypy doesn't allow monkey-patching functions
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**' # type: ignore # https://github.com/python/mypy/issues/708

        markdown = [
            '``` .py',
            'hello()',
            '```',
            '',
            '``` .py',
            'goodbye()',
            '```',
            '',
            ''
        ]
        expected = [
            '',
            '**py:hello()**',
            '',
            '',
            '',
            '**py:goodbye()**',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_nested_code(self):
        # type: () -> None
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code # type: ignore # mypy doesn't allow monkey-patching functions
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**' # type: ignore # https://github.com/python/mypy/issues/708

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

def bugdown_convert(text):
    # type: (Text) -> Text
    return bugdown.convert(text, message_realm=get_realm('zulip'))

class BugdownTest(TestCase):
    def load_bugdown_tests(self):
        # type: () -> Tuple[Dict[Text, Any], List[List[Text]]]
        test_fixtures = {}
        data_file = open(os.path.join(os.path.dirname(__file__), '../fixtures/bugdown-data.json'), 'r')
        data = ujson.loads('\n'.join(data_file.readlines()))
        for test in data['regular_tests']:
            test_fixtures[test['name']] = test

        return test_fixtures, data['linkify_tests']

    def test_bugdown_fixtures(self):
        # type: () -> None
        format_tests, linkify_tests = self.load_bugdown_tests()

        self.maxDiff = None # type: Optional[int]
        for name, test in six.iteritems(format_tests):
            converted = bugdown_convert(test['input'])

            print("Running Bugdown test %s" % (name,))
            self.assertEqual(converted, test['expected_output'])

        def replaced(payload, url, phrase=''):
            # type: (Text, Text, Text) -> Text
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
        self.maxDiff = None # type: Optional[int]
        with mock.patch('zerver.lib.url_preview.preview.link_embed_data_from_cache', return_value=None):
            for inline_url, reference, url in linkify_tests:
                try:
                    match = replaced(reference, url, phrase=inline_url)
                except TypeError:
                    match = reference
                converted = bugdown_convert(inline_url)
                self.assertEqual(match, converted)

    def test_inline_file(self):
        # type: () -> None
        msg = 'Check out this file file:///Volumes/myserver/Users/Shared/pi.py'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>Check out this file <a href="file:///Volumes/myserver/Users/Shared/pi.py" target="_blank" title="file:///Volumes/myserver/Users/Shared/pi.py">file:///Volumes/myserver/Users/Shared/pi.py</a></p>')

        with self.settings(ENABLE_FILE_LINKS=False):
            realm = Realm.objects.create(
                domain='file_links_test.example.com',
                string_id='file_links_test')
            bugdown.make_md_engine(
                realm.id,
                {'realm_filters': [[], u'file_links_test.example.com'], 'realm': [u'file_links_test.example.com', 'Realm name']})
            converted = bugdown.convert(msg, message_realm=realm)
            self.assertEqual(converted, '<p>Check out this file file:///Volumes/myserver/Users/Shared/pi.py</p>')

    def test_inline_youtube(self):
        # type: () -> None
        msg = 'Check out the debate: http://www.youtube.com/watch?v=hx1mjT73xYE'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="youtube-video message_inline_image"><a data-id="hx1mjT73xYE" href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg"></a></div>')

    def test_inline_dropbox(self):
        # type: () -> None
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

    def test_inline_dropbox_preview(self):
        # type: () -> None
        # Test photo album previews
        msg = 'https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5'
        image_info = {'image': 'https://photos-6.dropbox.com/t/2/AAAlawaeD61TyNewO5vVi-DGf2ZeuayfyHFdNTNzpGq-QA/12/271544745/jpeg/1024x1024/2/_/0/5/baby-piglet.jpg/CKnjvYEBIAIgBygCKAc/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0', 'desc': 'Shared with Dropbox', 'title': '1 photo'}
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=image_info):
            converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" target="_blank" title="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5">https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" target="_blank" title="1 photo"><img src="https://photos-6.dropbox.com/t/2/AAAlawaeD61TyNewO5vVi-DGf2ZeuayfyHFdNTNzpGq-QA/12/271544745/jpeg/1024x1024/2/_/0/5/baby-piglet.jpg/CKnjvYEBIAIgBygCKAc/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0"></a></div>')

    def test_inline_dropbox_negative(self):
        # type: () -> None
        # Make sure we're not overzealous in our conversion:
        msg = 'Look at the new dropbox logo: https://www.dropbox.com/static/images/home_logo.png'
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=None):
            converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at the new dropbox logo: <a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png">https://www.dropbox.com/static/images/home_logo.png</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png"><img src="https://www.dropbox.com/static/images/home_logo.png"></a></div>')

    def test_inline_dropbox_bad(self):
        # type: () -> None
        # Don't fail on bad dropbox links
        msg = "https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM"
        with mock.patch('zerver.lib.bugdown.fetch_open_graph_image', return_value=None):
            converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p><a href="https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM" target="_blank" title="https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM">https://zulip-test.dropbox.com/photos/cl/ROmr9K1XYtmpneM</a></p>')

    def test_twitter_id_extraction(self):
        # type: () -> None
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/#!/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/statuses/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858/'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/photo/1'), '410766290349879296')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/'), '410766290349879296')

    def test_inline_interesting_links(self):
        # type: () -> None
        def make_link(url):
            # type: (Text) -> Text
            return '<a href="%s" target="_blank" title="%s">%s</a>' % (url, url, url)

        normal_tweet_html = ('<a href="https://twitter.com/twitter" target="_blank"'
                             ' title="https://twitter.com/twitter">@twitter</a> '
                             'meets @seepicturely at #tcdisrupt cc.'
                             '<a href="https://twitter.com/boscomonkey" target="_blank"'
                             ' title="https://twitter.com/boscomonkey">@boscomonkey</a> '
                             '<a href="https://twitter.com/episod" target="_blank"'
                             ' title="https://twitter.com/episod">@episod</a> '
                             '<a href="http://t.co/6J2EgYM" target="_blank"'
                             ' title="http://t.co/6J2EgYM">http://instagram.com/p/MuW67/</a>')

        mention_in_link_tweet_html = """<a href="http://t.co/@foo" target="_blank" title="http://t.co/@foo">http://foo.com</a>"""

        media_tweet_html = ('<a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3">'
                            'http://twitter.com/NEVNBoston/status/421654515616849920/photo/1</a>')

        def make_inline_twitter_preview(url, tweet_html, image_html=''):
            # type: (Text, Text, Text) -> Text
            ## As of right now, all previews are mocked to be the exact same tweet
            return ('<div class="inline-preview-twitter">'
                    '<div class="twitter-tweet">'
                    '<a href="%s" target="_blank">'
                    '<img class="twitter-avatar"'
                    ' src="https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png">'
                    '</a>'
                    '<p>%s</p>'
                    '<span>- Eoin McMillan  (@imeoin)</span>'
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

    def test_fetch_tweet_data_settings_validation(self):
        # type: () -> None
        with self.settings(TEST_SUITE=False, TWITTER_CONSUMER_KEY=None):
            self.assertIs(None, bugdown.fetch_tweet_data('287977969287315459'))

    def test_realm_emoji(self):
        # type: () -> None
        def emoji_img(name, url):
            # type: (Text, Text) -> Text
            return '<img alt="%s" class="emoji" src="%s" title="%s">' % (name, get_camo_url(url), name)

        realm = get_realm('zulip')
        url = "https://zulip.com/test_realm_emoji.png"
        check_add_realm_emoji(realm, "test", url)

        # Needs to mock an actual message because that's how bugdown obtains the realm
        msg = Message(sender=get_user_profile_by_email("hamlet@zulip.com"))
        converted = bugdown.convert(":test:", message_realm=realm, message=msg)
        self.assertEqual(converted, '<p>%s</p>' % (emoji_img(':test:', url)))

        do_remove_realm_emoji(realm, 'test')
        converted = bugdown.convert(":test:", message_realm=realm, message=msg)
        self.assertEqual(converted, '<p>:test:</p>')

    def test_unicode_emoji(self):
        # type: () -> None
        msg = u'\u2615'  # ☕
        converted = bugdown_convert(msg)
        self.assertEqual(converted, u'<p><img alt="\u2615" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2615.png" title="\u2615"></p>')

        msg = u'\u2615\u2615'  # ☕☕
        converted = bugdown_convert(msg)
        self.assertEqual(converted, u'<p><img alt="\u2615" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2615.png" title="\u2615"><img alt="\u2615" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2615.png" title="\u2615"></p>')

    def test_realm_patterns(self):
        # type: () -> None
        realm = get_realm('zulip')
        url_format_string = r"https://trac.zulip.net/ticket/%(id)s"
        realm_filter = RealmFilter(realm=realm,
                                   pattern=r"#(?P<id>[0-9]{2,8})",
                                   url_format_string=url_format_string)
        realm_filter.save()
        self.assertEqual(
            realm_filter.__unicode__(),
            '<RealmFilter(zulip): #(?P<id>[0-9]{2,8})'
            ' https://trac.zulip.net/ticket/%(id)s>')

        msg = Message(sender=get_user_profile_by_email("othello@zulip.com"),
                      subject="#444")

        flush_per_request_caches()

        content = "We should fix #224 and #115, but not issue#124 or #1124z or [trac #15](https://trac.zulip.net/ticket/16) today."
        converted = bugdown.convert(content, message_realm=realm, message=msg)
        converted_subject = bugdown.subject_links(realm.id, msg.subject)

        self.assertEqual(converted, '<p>We should fix <a href="https://trac.zulip.net/ticket/224" target="_blank" title="https://trac.zulip.net/ticket/224">#224</a> and <a href="https://trac.zulip.net/ticket/115" target="_blank" title="https://trac.zulip.net/ticket/115">#115</a>, but not issue#124 or #1124z or <a href="https://trac.zulip.net/ticket/16" target="_blank" title="https://trac.zulip.net/ticket/16">trac #15</a> today.</p>')
        self.assertEqual(converted_subject, [u'https://trac.zulip.net/ticket/444'])

        RealmFilter(realm=realm, pattern=r'#(?P<id>[a-zA-Z]+-[0-9]+)',
                    url_format_string=r'https://trac.zulip.net/ticket/%(id)s').save()
        msg = Message(sender=get_user_profile_by_email('hamlet@zulip.com'))

        content = '#ZUL-123 was fixed and code was deployed to production, also #zul-321 was deployed to staging'
        converted = bugdown.convert(content, message_realm=realm, message=msg)

        self.assertEqual(converted, '<p><a href="https://trac.zulip.net/ticket/ZUL-123" target="_blank" title="https://trac.zulip.net/ticket/ZUL-123">#ZUL-123</a> was fixed and code was deployed to production, also <a href="https://trac.zulip.net/ticket/zul-321" target="_blank" title="https://trac.zulip.net/ticket/zul-321">#zul-321</a> was deployed to staging</p>')

    def test_maybe_update_realm_filters(self):
        # type: () -> None
        realm = get_realm('zulip')
        url_format_string = r"https://trac.zulip.net/ticket/%(id)s"
        realm_filter = RealmFilter(realm=realm,
                                   pattern=r"#(?P<id>[0-9]{2,8})",
                                   url_format_string=url_format_string)
        realm_filter.save()

        bugdown.realm_filter_data = {}
        bugdown.maybe_update_realm_filters(None)
        all_filters = bugdown.realm_filter_data
        zulip_filters = all_filters[realm.id]
        self.assertEqual(len(zulip_filters), 1)
        self.assertEqual(zulip_filters[0],
                         (u'#(?P<id>[0-9]{2,8})', u'https://trac.zulip.net/ticket/%(id)s', realm_filter.id))

    def test_flush_realm_filter(self):
        # type: () -> None
        realm = get_realm('zulip')

        def flush():
            # type: () -> None
            '''
            flush_realm_filter is a post-save hook, so calling it
            directly for testing is kind of awkward
            '''
            class Instance(object):
                realm_id = None # type: Optional[int]
            instance = Instance()
            instance.realm_id = realm.id
            flush_realm_filter(sender=None, instance=instance)

        def save_new_realm_filter():
            # type: () -> None
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

    def test_realm_patterns_negative(self):
        # type: () -> None
        realm = get_realm('zulip')
        RealmFilter(realm=realm, pattern=r"#(?P<id>[0-9]{2,8})",
                    url_format_string=r"https://trac.zulip.net/ticket/%(id)s").save()
        boring_msg = Message(sender=get_user_profile_by_email("othello@zulip.com"),
                             subject=u"no match here")
        converted_boring_subject = bugdown.subject_links(realm.id, boring_msg.subject)
        self.assertEqual(converted_boring_subject, [])

    def test_is_status_message(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("othello@zulip.com")
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

    def test_alert_words(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("othello@zulip.com")
        do_set_alert_words(user_profile, ["ALERTWORD", "scaryword"])
        msg = Message(sender=user_profile, sending_client=get_client("test"))
        realm_alert_words = alert_words_in_realm(user_profile.realm)

        def render(msg, content):
            # type: (Message, Text) -> Text
            return render_markdown(msg,
                                   content,
                                   realm_alert_words=realm_alert_words,
                                   message_users={user_profile})

        content = "We have an ALERTWORD day today!"
        self.assertEqual(render(msg, content), "<p>We have an ALERTWORD day today!</p>")
        self.assertEqual(msg.user_ids_with_alert_words, set([user_profile.id]))

        msg = Message(sender=user_profile, sending_client=get_client("test"))
        content = "We have a NOTHINGWORD day today!"
        self.assertEqual(render(msg, content), "<p>We have a NOTHINGWORD day today!</p>")
        self.assertEqual(msg.user_ids_with_alert_words, set())

    def test_mention_wildcard(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@all test"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" data-user-email="*" data-user-id="*">'
                         '@all'
                         '</span> test</p>')
        self.assertTrue(msg.mentions_wildcard)

    def test_mention_everyone(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=user_profile, sending_client=get_client("test"))

        content = "@everyone test"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" data-user-email="*" data-user-id="*">@everyone</span> test</p>')
        self.assertTrue(msg.mentions_wildcard)

    def test_mention_single(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        user_id = user_profile.id

        content = "@**King Hamlet**"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" '
                         'data-user-email="%s" '
                         'data-user-id="%s">'
                         '@King Hamlet</span></p>' % ('hamlet@zulip.com', user_id))
        self.assertEqual(msg.mentions_user_ids, set([user_profile.id]))

    def test_mention_shortname(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        user_id = user_profile.id

        content = "@**hamlet**"
        self.assertEqual(render_markdown(msg, content),
                         '<p><span class="user-mention" '
                         'data-user-email="%s" data-user-id="%s">'
                         '@King Hamlet</span></p>' % ('hamlet@zulip.com', user_id))
        self.assertEqual(msg.mentions_user_ids, set([user_profile.id]))

    def test_mention_multiple(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        hamlet = get_user_profile_by_email("hamlet@zulip.com")
        cordelia = get_user_profile_by_email("cordelia@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "@**King Hamlet** and @**cordelia**, check this out"
        self.assertEqual(render_markdown(msg, content),
                         '<p>'
                         '<span class="user-mention" '
                         'data-user-email="%s" '
                         'data-user-id="%s">@King Hamlet</span> and '
                         '<span class="user-mention" '
                         'data-user-email="%s" '
                         'data-user-id="%s">@Cordelia Lear</span>, '
                         'check this out</p>' % (hamlet.email, hamlet.id, cordelia.email, cordelia.id))
        self.assertEqual(msg.mentions_user_ids, set([hamlet.id, cordelia.id]))

    def test_mention_invalid(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "Hey @**Nonexistent User**"
        self.assertEqual(render_markdown(msg, content),
                         '<p>Hey @<strong>Nonexistent User</strong></p>')
        self.assertEqual(msg.mentions_user_ids, set())

    def test_stream_single(self):
        # type: () -> None
        denmark = get_stream('Denmark', get_realm('zulip'))
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = "#**Denmark**"
        self.assertEqual(
            render_markdown(msg, content),
            '<p><a class="stream" data-stream-id="{d.id}" href="/#narrow/stream/Denmark">#{d.name}</a></p>'.format(
                d=denmark
            ))

    def test_stream_multiple(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        realm = get_realm('zulip')
        denmark = get_stream('Denmark', realm)
        scotland = get_stream('Scotland', realm)
        content = "Look to #**Denmark** and #**Scotland**, there something"
        self.assertEqual(render_markdown(msg, content),
                         '<p>Look to '
                         '<a class="stream" '
                         'data-stream-id="{denmark.id}" '
                         'href="/#narrow/stream/Denmark">#{denmark.name}</a> and '
                         '<a class="stream" '
                         'data-stream-id="{scotland.id}" '
                         'href="/#narrow/stream/Scotland">#{scotland.name}</a>, '
                         'there something</p>'.format(denmark=denmark, scotland=scotland))

    def test_stream_case_sensitivity(self):
        # type: () -> None
        realm = get_realm('zulip')
        case_sens = Stream.objects.create(name='CaseSens', realm=realm)
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = "#**CaseSens**"
        self.assertEqual(
            render_markdown(msg, content),
            '<p><a class="stream" data-stream-id="{s.id}" href="/#narrow/stream/{s.name}">#{s.name}</a></p>'.format(
                s=case_sens
            ))

    def test_stream_case_sensitivity_nonmatching(self):
        # type: () -> None
        """#StreamName requires the stream be spelled with the correct case
        currently.  If we change that in the future, we'll need to change this
        test."""
        realm = get_realm('zulip')
        Stream.objects.create(name='CaseSens', realm=realm)
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = "#**casesens**"
        self.assertEqual(
            render_markdown(msg, content),
            '<p>#<strong>casesens</strong></p>')

    def test_stream_unicode(self):
        # type: () -> None
        realm = get_realm('zulip')
        uni = Stream.objects.create(name=u'привет', realm=realm)
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))
        content = u"#**привет**"
        self.assertEqual(
            render_markdown(msg, content),
            u'<p><a class="stream" data-stream-id="{s.id}" href="/#narrow/stream/{url}">#{s.name}</a></p>'.format(
                s=uni,
                url=urllib.parse.quote(force_str(uni.name))
            ))

    def test_stream_invalid(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        msg = Message(sender=sender_user_profile, sending_client=get_client("test"))

        content = "There #**Nonexistentstream**"
        self.assertEqual(render_markdown(msg, content),
                         '<p>There #<strong>Nonexistentstream</strong></p>')
        self.assertEqual(msg.mentions_user_ids, set())

    def test_stream_subscribe_button_simple(self):
        # type: () -> None
        msg = '!_stream_subscribe_button(simple)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple">'
            '<button class="inline-subscribe-button btn">Subscribe to simple</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            '</p>'
        )

    def test_stream_subscribe_button_in_name(self):
        # type: () -> None
        msg = '!_stream_subscribe_button(simple (not\\))'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple (not)">'
            '<button class="inline-subscribe-button btn">Subscribe to simple (not)</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            '</p>'
        )

    def test_stream_subscribe_button_after_name(self):
        # type: () -> None
        msg = '!_stream_subscribe_button(simple) (not)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple">'
            '<button class="inline-subscribe-button btn">Subscribe to simple</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            ' (not)</p>'
        )

    def test_stream_subscribe_button_slash(self):
        # type: () -> None
        msg = '!_stream_subscribe_button(simple\\\\)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple\\">'
            '<button class="inline-subscribe-button btn">Subscribe to simple\\</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            '</p>'
        )

    def test_in_app_modal_link(self):
        # type: () -> None
        msg = '!modal_link(#settings, Settings page)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<a data-toggle="modal" href="#settings" title="#settings">Settings page</a>'
            '</p>'
        )

    def test_image_preview_title(self):
        # type: () -> None
        msg = '[My favorite image](https://example.com/testimage.png)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<a href="https://example.com/testimage.png" target="_blank" title="https://example.com/testimage.png">My favorite image</a>'
            '</p>\n'
            '<div class="message_inline_image">'
            '<a href="https://example.com/testimage.png" target="_blank" title="My favorite image">'
            '<img src="https://example.com/testimage.png">'
            '</a>'
            '</div>'
        )

    def test_mit_rendering(self):
        # type: () -> None
        """Test the markdown configs for the MIT Zephyr mirroring system;
        verifies almost all inline patterns are disabled, but
        inline_interesting_links is still enabled"""
        msg = "**test**"
        realm = get_realm("zephyr")
        client = get_client("zephyr_mirror")
        message = Message(sending_client=client,
                          sender=get_user_profile_by_email("sipbtest@mit.edu"))
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

class BugdownApiTests(ZulipTestCase):
    def test_render_message_api(self):
        # type: () -> None
        content = 'That is a **bold** statement'
        result = self.client_post(
            '/api/v1/messages/render',
            dict(content=content),
            **self.api_auth('othello@zulip.com')
        )
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['rendered'],
                         u'<p>That is a <strong>bold</strong> statement</p>')

    def test_render_mention_stream_api(self):
        # type: () -> None
        """Determines whether we're correctly passing the realm context"""
        content = 'This mentions #**Denmark** and @**King Hamlet**.'
        result = self.client_post(
            '/api/v1/messages/render',
            dict(content=content),
            **self.api_auth('othello@zulip.com')
        )
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        user_id = get_user_profile_by_email('hamlet@zulip.com').id
        self.assertEqual(data['rendered'],
                         u'<p>This mentions <a class="stream" data-stream-id="%s" href="/#narrow/stream/Denmark">#Denmark</a> and <span class="user-mention" data-user-email="%s" data-user-id="%s">@King Hamlet</span>.</p>' % (get_stream("Denmark", get_realm("zulip")).id, 'hamlet@zulip.com', user_id))

class BugdownErrorTests(ZulipTestCase):
    def test_bugdown_error_handling(self):
        # type: () -> None
        with self.simulated_markdown_failure():
            with self.assertRaises(bugdown.BugdownRenderingException):
                bugdown_convert('')

    def test_send_message_errors(self):
        # type: () -> None

        message = 'whatever'
        with self.simulated_markdown_failure():
            # We don't use assertRaisesRegex because it seems to not
            # handle i18n properly here on some systems.
            with self.assertRaises(JsonableError):
                self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, message)


class BugdownAvatarTestCase(ZulipTestCase):
    def test_avatar_with_id(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))

        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        msg = '!avatar({0})'.format(user_profile.email)
        converted = bugdown.convert(msg, message=message)
        values = {'email': user_profile.email, 'id': user_profile.id}
        self.assertEqual(
            converted,
            '<p><img alt="{email}" class="message_body_gravatar" src="/avatar/{id}?s=30" title="{email}"></p>'.format(**values))

    def test_avatar_of_unregistered_user(self):
        # type: () -> None
        sender_user_profile = get_user_profile_by_email("othello@zulip.com")
        message = Message(sender=sender_user_profile, sending_client=get_client("test"))

        email = 'fakeuser@example.com'
        msg = '!avatar({0})'.format(email)
        converted = bugdown.convert(msg, message=message)
        self.assertEqual(
            converted,
            '<p><img alt="{0}" class="message_body_gravatar" src="/avatar/{0}?s=30" title="{0}"></p>'.format(email))
