# -*- coding: utf-8 -*-
from django.conf import settings
from django.test import TestCase

from zerver.lib import bugdown
from zerver.lib.actions import (
    do_add_realm_emoji,
    do_remove_realm_emoji,
    get_realm,
)

from zerver.models import (
    get_user_profile_by_email,
    Message,
    RealmFilter,
)

import os
import ujson

class FencedBlockPreprocessorTest(TestCase):
    def test_simple_quoting(self):
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
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**'

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
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**'

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
    return bugdown.convert(text, "zulip.com")

class BugdownTest(TestCase):
    def common_bugdown_test(self, text, expected):
        converted = bugdown_convert(text)
        self.assertEqual(converted, expected)

    def load_bugdown_tests(self):
        test_fixtures = {}
        data_file = open(os.path.join(os.path.dirname(__file__), 'fixtures/bugdown-data.json'), 'r')
        data = ujson.loads('\n'.join(data_file.readlines()))
        for test in data['regular_tests']:
            test_fixtures[test['name']] = test

        return test_fixtures, data['linkify_tests']

    def test_bugdown_fixtures(self):
        format_tests, linkify_tests = self.load_bugdown_tests()

        self.maxDiff = None
        for name, test in format_tests.iteritems():
            converted = bugdown_convert(test['input'])

            print "Running Bugdown test %s" % (name,)
            self.assertEqual(converted, test['expected_output'])

        def replaced(payload, url, phrase=''):
            target = " target=\"_blank\""
            if url[:4] == 'http':
                href = url
            elif '@' in url:
                href = 'mailto:' + url
                target = ""
            else:
                href = 'http://' + url
            return payload % ("<a href=\"%s\"%s title=\"%s\">%s</a>" % (href, target, href, url),)


        print "Running Bugdown Linkify tests"
        self.maxDiff = None
        for inline_url, reference, url in linkify_tests:
            try:
                match = replaced(reference, url, phrase=inline_url)
            except TypeError:
                match = reference
            converted = bugdown_convert(inline_url)
            self.assertEqual(match, converted)

    def test_inline_youtube(self):
        msg = 'Check out the debate: http://www.youtube.com/watch?v=hx1mjT73xYE'
        converted = bugdown_convert(msg)

        if settings.USING_EMBEDLY:
            self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<iframe width="250" height="141" src="http://www.youtube.com/embed/hx1mjT73xYE?feature=oembed" frameborder="0" allowfullscreen></iframe>')
        else:
            self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="message_inline_image"><a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg"></a></div>')

    def test_inline_dropbox(self):
        return  # The dropbox url format changed
        msg = 'Look at how hilarious our old office was: https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at how hilarious our old office was: <a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" target="_blank" title="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG">https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" target="_blank" title="IMG_0923.JPG"><img src="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG?dl=1"></a></div>')

        msg = 'Look at my hilarious drawing folder: https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl='
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at my hilarious drawing folder: <a href="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=" target="_blank" title="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=">https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=</a></p>\n<div class="message_inline_ref"><a href="https://www.dropbox.com/sh/cm39k9e04z7fhim/AAAII5NK-9daee3FcF41anEua?dl=" target="_blank" title="Saves"><img src="https://www.dropbox.com/static/images/icons128/folder_dropbox.png"></a><div><div class="message_inline_image_title">Saves</div><desc class="message_inline_image_desc"></desc></div></div>')

        # Test photo album previews
        msg = 'https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" target="_blank" title="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5">https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/sc/tditp9nitko60n5/03rEiZldy5" target="_blank" title="1 photo"><img src="https://photos-3.dropbox.com/t/0/AAAOZdw61-X_zSVRQj-IKZ9rDucmgSTm3Ff6Tc-lJqdvdA/12/271544745/jpeg/320x320/1/_/0/5/baby-piglet.jpg/tditp9nitko60n5/AADX03VAIrQlTl28CtujDcMla/0"></a></div>')

        # Make sure we're not overzealous in our conversion:
        msg = 'Look at the new dropbox logo: https://www.dropbox.com/static/images/home_logo.png'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at the new dropbox logo: <a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png">https://www.dropbox.com/static/images/home_logo.png</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png"><img src="https://www.dropbox.com/static/images/home_logo.png"></a></div>')

        # Don't fail on bad dropbox links
        msg = "https://meta-dbdev.dev.corp.dropbox.com/photos/cl/ROmr9K1XYtmpneM"
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p><a href="https://meta-dbdev.dev.corp.dropbox.com/photos/cl/ROmr9K1XYtmpneM" target="_blank" title="https://meta-dbdev.dev.corp.dropbox.com/photos/cl/ROmr9K1XYtmpneM">https://meta-dbdev.dev.corp.dropbox.com/photos/cl/ROmr9K1XYtmpneM</a></p>\n<div class="message_inline_image"><a href="https://meta-dbdev.dev.corp.dropbox.com/photos/cl/ROmr9K1XYtmpneM" target="_blank" title="ROmr9K1XYtmpneM"><img src="/static/images/preview_fail.png"></a></div>')

    def test_twitter_id_extraction(self):
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/#!/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/statuses/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858/'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/photo/1'), '410766290349879296')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/'), '410766290349879296')

    def test_inline_interesting_links(self):
        def make_link(url):
            return '<a href="%s" target="_blank" title="%s">%s</a>' % (url, url, url)

        normal_tweet_html = """<a href="https://twitter.com/twitter" target="_blank" title="https://twitter.com/twitter">@twitter</a> meets <a href="https://twitter.com/seepicturely" target="_blank" title="https://twitter.com/seepicturely">@seepicturely</a> at #tcdisrupt cc.<a href="https://twitter.com/boscomonkey" target="_blank" title="https://twitter.com/boscomonkey">@boscomonkey</a> <a href="https://twitter.com/episod" target="_blank" title="https://twitter.com/episod">@episod</a> <a href="http://t.co/6J2EgYM" target="_blank" title="http://t.co/6J2EgYM">http://instagram.com/p/MuW67/</a>"""

        mention_in_link_tweet_html = """<a href="http://t.co/@foo" target="_blank" title="http://t.co/@foo">http://foo.com</a>"""

        media_tweet_html = """<a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3">http://twitter.com/NEVNBoston/status/421654515616849920/photo/1</a>"""

        def make_inline_twitter_preview(url, tweet_html, image_html=''):
            ## As of right now, all previews are mocked to be the exact same tweet
            return """<div class="inline-preview-twitter"><div class="twitter-tweet"><a href="%s" target="_blank"><img class="twitter-avatar" src="https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png"></a><p>%s</p><span>- Eoin McMillan  (@imeoin)</span>%s</div></div>""" % (url, tweet_html, image_html)

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
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://www.twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('http://www.twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        msg = 'https://www.twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('https://www.twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('https://www.twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        msg = 'http://twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        # A max of 3 will be converted
        msg = 'http://twitter.com/wdaher/status/287977969287315456 http://twitter.com/wdaher/status/287977969287315457 http://twitter.com/wdaher/status/287977969287315457 http://twitter.com/wdaher/status/287977969287315457'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s %s %s %s</p>\n%s%s%s' % (make_link('http://twitter.com/wdaher/status/287977969287315456'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456', normal_tweet_html),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315457', normal_tweet_html),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315457', normal_tweet_html)))

        # Tweet has a mention in a URL, only the URL is linked
        msg = 'http://twitter.com/wdaher/status/287977969287315458'

        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315458'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315458', mention_in_link_tweet_html)))

        # Tweet with an image
        msg = 'http://twitter.com/wdaher/status/287977969287315459'

        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315459'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315459', media_tweet_html, """<div class="twitter-image"><a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3"><img src="https://pbs.twimg.com/media/BdoEjD4IEAIq86Z.jpg:small"></a></div>""")))

    def test_realm_emoji(self):
        def emoji_img(name, url):
            return '<img alt="%s" class="emoji" src="%s" title="%s">' % (name, url, name)

        zulip_realm = get_realm('zulip.com')
        url = "https://zulip.com/test_realm_emoji.png"
        do_add_realm_emoji(zulip_realm, "test", url)

        # Needs to mock an actual message because that's how bugdown obtains the realm
        msg = Message(sender=get_user_profile_by_email("hamlet@zulip.com"))
        converted = bugdown.convert(":test:", "zulip.com", msg)
        self.assertEqual(converted, '<p>%s</p>' %(emoji_img(':test:', url)))

        do_remove_realm_emoji(zulip_realm, 'test')
        converted = bugdown.convert(":test:", "zulip.com", msg)
        self.assertEqual(converted, '<p>:test:</p>')

    def test_realm_patterns(self):
        RealmFilter(realm=get_realm('zulip.com'), pattern=r"#(?P<id>[0-9]{2,8})",
                    url_format_string=r"https://trac.zulip.net/ticket/%(id)s").save()
        msg = Message(sender=get_user_profile_by_email("othello@zulip.com"))

        content = "We should fix #224 and #115, but not issue#124 or #1124z or [trac #15](https://trac.zulip.net/ticket/16) today."
        converted = bugdown.convert(content, realm_domain='zulip.com', message=msg)

        self.assertEqual(converted, '<p>We should fix <a href="https://trac.zulip.net/ticket/224" target="_blank" title="https://trac.zulip.net/ticket/224">#224</a> and <a href="https://trac.zulip.net/ticket/115" target="_blank" title="https://trac.zulip.net/ticket/115">#115</a>, but not issue#124 or #1124z or <a href="https://trac.zulip.net/ticket/16" target="_blank" title="https://trac.zulip.net/ticket/16">trac #15</a> today.</p>')

    def test_stream_subscribe_button_simple(self):
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
        msg = '!modal_link(#settings, Settings page)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<a data-toggle="modal" href="#settings" title="#settings">Settings page</a>'
            '</p>'
        )

    def test_mit_rendering(self):
        msg = "**test**"
        converted = bugdown.convert(msg, "mit.edu/zephyr_mirror")
        self.assertEqual(
            converted,
            "<p>**test**</p>",
            )
        msg = "* test"
        converted = bugdown.convert(msg, "mit.edu/zephyr_mirror")
        self.assertEqual(
            converted,
            "<p>* test</p>",
            )
        msg = "https://lists.debian.org/debian-ctte/2014/02/msg00173.html"
        converted = bugdown.convert(msg, "mit.edu/zephyr_mirror")
        self.assertEqual(
            converted,
            '<p><a href="https://lists.debian.org/debian-ctte/2014/02/msg00173.html" target="_blank" title="https://lists.debian.org/debian-ctte/2014/02/msg00173.html">https://lists.debian.org/debian-ctte/2014/02/msg00173.html</a></p>',
            )

