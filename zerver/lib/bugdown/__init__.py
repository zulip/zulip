from __future__ import absolute_import
# Zulip's main markdown implementation.  See docs/markdown.md for
# detailed documentation on our markdown syntax.
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar, Union
from typing.re import Match

import markdown
import logging
import traceback
from six.moves import urllib
import re
import os.path
import glob
import twitter
import platform
import time
import httplib2
import itertools
from six.moves import urllib
import xml.etree.cElementTree as etree
from xml.etree.cElementTree import Element, SubElement

from collections import defaultdict

import requests

from django.core import mail
from django.conf import settings

from zerver.lib.avatar  import gravatar_hash
from zerver.lib.bugdown import codehilite
from zerver.lib.bugdown import fenced_code
from zerver.lib.bugdown.fenced_code import FENCE_RE
from zerver.lib.camo import get_camo_url
from zerver.lib.timeout import timeout, TimeoutExpired
from zerver.lib.cache import cache_with_key, cache_get_many, cache_set_many
from zerver.models import Message
import zerver.lib.alert_words as alert_words
import zerver.lib.mention as mention
from zerver.lib.str_utils import force_text, force_str
import six
from six.moves import range, html_parser
from six import text_type

if six.PY3:
    import html

# Format version of the bugdown rendering; stored along with rendered
# messages so that we can efficiently determine what needs to be re-rendered
version = 1

_T = TypeVar('_T')
# We need to avoid this running at runtime, but mypy will see this.
# The problem is that under python 2, Element isn't exactly a type,
# which means that at runtime Union causes this to blow up.
if False:
    # mypy requires the Optional to be inside Union
    ElementStringNone = Union[Element, Optional[text_type]]

def unescape(s):
    # type: (text_type) -> (text_type)
    if six.PY2:
        return html_parser.HTMLParser().unescape(s)
    else:
        return html.unescape(s)

def list_of_tlds():
    # type: () -> List[text_type]
    # HACK we manually blacklist .py
    blacklist = [u'PY\n', ]

    # tlds-alpha-by-domain.txt comes from http://data.iana.org/TLD/tlds-alpha-by-domain.txt
    tlds_file = os.path.join(os.path.dirname(__file__), 'tlds-alpha-by-domain.txt')
    tlds = [force_text(tld).lower().strip() for tld in open(tlds_file, 'r')
                if tld not in blacklist and not tld[0].startswith('#')]
    tlds.sort(key=len, reverse=True)
    return tlds

def walk_tree(root, processor, stop_after_first=False):
    # type: (Element, Callable[[Element], Optional[_T]], bool) -> List[_T]
    results = []
    stack = [root]

    while stack:
        currElement = stack.pop()
        for child in currElement.getchildren():
            if child.getchildren():
                stack.append(child)

            result = processor(child)
            if result is not None:
                results.append(result)
                if stop_after_first:
                    return results

    return results

# height is not actually used
def add_a(root, url, link, height="", title=None, desc=None,
          class_attr="message_inline_image"):
    # type: (Element, text_type, text_type, text_type, Optional[text_type], Optional[text_type], text_type) -> None
    title = title if title is not None else url_filename(link)
    title = title if title else ""
    desc = desc if desc is not None else ""

    div = markdown.util.etree.SubElement(root, "div")
    div.set("class", class_attr)
    a = markdown.util.etree.SubElement(div, "a")
    a.set("href", link)
    a.set("target", "_blank")
    a.set("title", title )
    img = markdown.util.etree.SubElement(a, "img")
    img.set("src", url)
    if class_attr == "message_inline_ref":
        summary_div = markdown.util.etree.SubElement(div, "div")
        title_div = markdown.util.etree.SubElement(summary_div, "div")
        title_div.set("class", "message_inline_image_title")
        title_div.text = title
        desc_div = markdown.util.etree.SubElement(summary_div, "desc")
        desc_div.set("class", "message_inline_image_desc")

@cache_with_key(lambda tweet_id: tweet_id, cache_name="database", with_statsd_key="tweet_data")
def fetch_tweet_data(tweet_id):
    # type: (text_type) -> Optional[Dict[text_type, Any]]
    if settings.TEST_SUITE:
        from . import testing_mocks
        res = testing_mocks.twitter(tweet_id)
    else:
        creds = {
            'consumer_key': settings.TWITTER_CONSUMER_KEY,
            'consumer_secret': settings.TWITTER_CONSUMER_SECRET,
            'access_token_key': settings.TWITTER_ACCESS_TOKEN_KEY,
            'access_token_secret': settings.TWITTER_ACCESS_TOKEN_SECRET,
        }
        if not all(creds.values()):
           return None

        try:
            api = twitter.Api(**creds)
            # Sometimes Twitter hangs on responses.  Timing out here
            # will cause the Tweet to go through as-is with no inline
            # preview, rather than having the message be rejected
            # entirely. This timeout needs to be less than our overall
            # formatting timeout.
            tweet = timeout(3, api.GetStatus, tweet_id)
            res = tweet.AsDict()
        except AttributeError:
            logging.error('Unable to load twitter api, you may have the wrong '
                          'library installed, see https://github.com/zulip/zulip/issues/86')
            return None
        except TimeoutExpired as e:
            # We'd like to try again later and not cache the bad result,
            # so we need to re-raise the exception (just as though
            # we were being rate-limited)
            raise
        except twitter.TwitterError as e:
            t = e.args[0]
            if len(t) == 1 and ('code' in t[0]) and (t[0]['code'] == 34):
                # Code 34 means that the message doesn't exist; return
                # None so that we will cache the error
                return None
            elif len(t) == 1 and ('code' in t[0]) and (t[0]['code'] == 88 or
                                                       t[0]['code'] == 130):
                # Code 88 means that we were rate-limited and 130
                # means Twitter is having capacity issues; either way
                # just raise the error so we don't cache None and will
                # try again later.
                raise
            else:
                # It's not clear what to do in cases of other errors,
                # but for now it seems reasonable to log at error
                # level (so that we get notified), but then cache the
                # failure to proceed with our usual work
                logging.error(traceback.format_exc())
                return None
    return res

HEAD_START_RE = re.compile(u'^head[ >]')
HEAD_END_RE = re.compile(u'^/head[ >]')
META_START_RE = re.compile(u'^meta[ >]')
META_END_RE = re.compile(u'^/meta[ >]')

def fetch_open_graph_image(url):
    # type: (text_type) -> Optional[Dict[str, Any]]
    in_head = False
    # HTML will auto close meta tags, when we start the next tag add a closing tag if it has not been closed yet.
    last_closed = True
    head = []

    # TODO: What if response content is huge? Should we get headers first?
    try:
        content = requests.get(url, timeout=1).text
    except:
        return None

    # Extract the head and meta tags
    # All meta tags are self closing, have no children or are closed
    # automatically.
    for part in content.split('<'):
        if not in_head and HEAD_START_RE.match(part):
            # Started the head node output it to have a document root
            in_head = True
            head.append('<head>')
        elif in_head and HEAD_END_RE.match(part):
            # Found the end of the head close any remaining tag then stop
            # processing
            in_head = False
            if not last_closed:
                last_closed = True
                head.append('</meta>')
            head.append('</head>')
            break

        elif in_head and META_START_RE.match(part):
            # Found a meta node copy it
            if not last_closed:
                head.append('</meta>')
                last_closed = True
            head.append('<')
            head.append(part)
            if '/>' not in part:
                last_closed = False

        elif in_head and META_END_RE.match(part):
            # End of a meta node just copy it to close the tag
            head.append('<')
            head.append(part)
            last_closed = True

    try:
        doc = etree.fromstring(''.join(head))
    except etree.ParseError:
        return None
    og_image = doc.find('meta[@property="og:image"]')
    og_title = doc.find('meta[@property="og:title"]')
    og_desc = doc.find('meta[@property="og:description"]')
    title = None
    desc = None
    if og_image is not None:
        image = og_image.get('content')
    else:
        return None
    if og_title is not None:
        title = og_title.get('content')
    if og_desc is not None:
        desc = og_desc.get('content')
    return {'image': image, 'title': title, 'desc': desc}

def get_tweet_id(url):
    # type: (text_type) -> Optional[text_type]
    parsed_url = urllib.parse.urlparse(url)
    if not (parsed_url.netloc == 'twitter.com' or parsed_url.netloc.endswith('.twitter.com')):
        return None
    to_match = parsed_url.path
    # In old-style twitter.com/#!/wdaher/status/1231241234-style URLs, we need to look at the fragment instead
    if parsed_url.path == '/' and len(parsed_url.fragment) > 5:
        to_match= parsed_url.fragment

    tweet_id_match = re.match(r'^!?/.*?/status(es)?/(?P<tweetid>\d{10,18})(/photo/[0-9])?/?$', to_match)
    if not tweet_id_match:
        return None
    return tweet_id_match.group("tweetid")

class InlineHttpsProcessor(markdown.treeprocessors.Treeprocessor):
    def run(self, root):
        # type: (Element) -> None
        # Get all URLs from the blob
        found_imgs = walk_tree(root, lambda e: e if e.tag == "img" else None)
        for img in found_imgs:
            url = img.get("src")
            if not url.startswith("http://"):
                # Don't rewrite images on our own site (e.g. emoji).
                continue
            img.set("src", get_camo_url(url))

class InlineInterestingLinkProcessor(markdown.treeprocessors.Treeprocessor):
    TWITTER_MAX_IMAGE_HEIGHT = 400
    TWITTER_MAX_TO_PREVIEW = 3

    def __init__(self, md, bugdown):
        # type: (markdown.Markdown, Bugdown) -> None
        # Passing in bugdown for access to config to check if realm is zulip.com
        self.bugdown = bugdown
        markdown.treeprocessors.Treeprocessor.__init__(self, md)

    def is_image(self, url):
        # type: (text_type) -> bool
        if not settings.INLINE_IMAGE_PREVIEW:
            return False
        parsed_url = urllib.parse.urlparse(url)
        # List from http://support.google.com/chromeos/bin/answer.py?hl=en&answer=183093
        for ext in [".bmp", ".gif", ".jpg", "jpeg", ".png", ".webp"]:
            if parsed_url.path.lower().endswith(ext):
                return True
        return False

    def dropbox_image(self, url):
        # type: (text_type) -> Optional[Dict]
        # TODO: specify details of returned Dict
        parsed_url = urllib.parse.urlparse(url)
        if (parsed_url.netloc == 'dropbox.com' or parsed_url.netloc.endswith('.dropbox.com')):
            is_album = parsed_url.path.startswith('/sc/') or parsed_url.path.startswith('/photos/')
            # Only allow preview Dropbox shared links
            if not (parsed_url.path.startswith('/s/') or
                    parsed_url.path.startswith('/sh/') or
                    is_album):
                return None

            # Try to retrieve open graph protocol info for a preview
            # This might be redundant right now for shared links for images.
            # However, we might want to make use of title and description
            # in the future. If the actual image is too big, we might also
            # want to use the open graph image.
            image_info = fetch_open_graph_image(url)

            is_image = is_album or self.is_image(url)

            # If it is from an album or not an actual image file,
            # just use open graph image.
            if is_album or not is_image:
                # Failed to follow link to find an image preview so
                # use placeholder image and guess filename
                if image_info is None:
                    return None

                image_info["is_image"] = is_image
                return image_info

            # Otherwise, try to retrieve the actual image.
            # This is because open graph image from Dropbox may have padding
            # and gifs do not work.
            # TODO: What if image is huge? Should we get headers first?
            if image_info is None:
                image_info = dict()
            image_info['is_image'] = True
            parsed_url_list = list(parsed_url)
            parsed_url_list[4] = "dl=1" # Replaces query
            image_info["image"] = urllib.parse.urlunparse(parsed_url_list)

            return image_info
        return None

    def youtube_image(self, url):
        # type: (text_type) -> Optional[text_type]
        if not settings.INLINE_IMAGE_PREVIEW:
            return None
        # Youtube video id extraction regular expression from http://pastebin.com/KyKAFv1s
        # If it matches, match.group(2) is the video id.
        youtube_re = r'^((?:https?://)?(?:youtu\.be/|(?:\w+\.)?youtube(?:-nocookie)?\.com/)' + \
                     r'(?:(?:(?:v|embed)/)|(?:(?:watch(?:_popup)?(?:\.php)?)?(?:\?|#!?)(?:.+&)?v=)))' + \
                     r'?([0-9A-Za-z_-]+)(?(1).+)?$'
        match = re.match(youtube_re, url)
        if match is None:
            return None
        return "https://i.ytimg.com/vi/%s/default.jpg" % (match.group(2),)

    def twitter_text(self, text, urls, user_mentions, media):
        # type: (text_type, List[Dict[text_type, text_type]], List[Dict[text_type, Any]], List[Dict[text_type, Any]]) -> Element
        """
        Use data from the twitter API to turn links, mentions and media into A
        tags.

        This works by using the urls, user_mentions and media data from the
        twitter API.

        The first step is finding the locations of the URLs, mentions and media
        in the text. For each match we build a dictionary with the start
        location, end location, the URL to link to, and the text to show in the
        link.

        Next we sort the matches by start location. And for each we add the
        text from the end of the last link to the start of the current link to
        the output. The text needs to added to the text attribute of the first
        node (the P tag) or the tail the last link created.

        Finally we add any remaining text to the last node.
        """

        to_linkify = [] # type: List[Dict[text_type, Any]]
        # Build dicts for URLs
        for url_data in urls:
            short_url = url_data["url"]
            full_url = url_data["expanded_url"]
            for match in re.finditer(re.escape(short_url), text, re.IGNORECASE):
                to_linkify.append({
                    'start': match.start(),
                    'end': match.end(),
                    'url': short_url,
                    'text': full_url,
                })
        # Build dicts for mentions
        for user_mention in user_mentions:
            screen_name = user_mention['screen_name']
            mention_string = u'@' + screen_name
            for match in re.finditer(re.escape(mention_string), text, re.IGNORECASE):
                to_linkify.append({
                    'start': match.start(),
                    'end': match.end(),
                    'url': u'https://twitter.com/' + force_text(urllib.parse.quote(force_str(screen_name))),
                    'text': mention_string,
                })
        # Build dicts for media
        for media_item in media:
            short_url = media_item['url']
            expanded_url = media_item['expanded_url']
            for match in re.finditer(re.escape(short_url), text, re.IGNORECASE):
                to_linkify.append({
                    'start': match.start(),
                    'end': match.end(),
                    'url': short_url,
                    'text': expanded_url,
                })

        to_linkify.sort(key=lambda x: x['start'])
        p = current_node = markdown.util.etree.Element('p')

        def set_text(text):
            # type: (text_type) -> None
            """
            Helper to set the text or the tail of the current_node
            """
            if current_node == p:
                current_node.text = text
            else:
                current_node.tail = text

        current_index = 0
        for link in to_linkify:
            # The text we want to link starts in already linked text skip it
            if link['start'] < current_index:
                continue
            # Add text from the end of last link to the start of the current
            # link
            set_text(text[current_index:link['start']])
            current_index = link['end']
            current_node = a = url_to_a(link['url'], link['text'])
            p.append(a)

        # Add any unused text
        set_text(text[current_index:])
        return p

    def twitter_link(self, url):
        # type: (text_type) -> Optional[Element]
        tweet_id = get_tweet_id(url)

        if tweet_id is None:
            return None

        try:
            res = fetch_tweet_data(tweet_id)
            if res is None:
                return None
            user = res['user'] # type: Dict[text_type, Any]
            tweet = markdown.util.etree.Element("div")
            tweet.set("class", "twitter-tweet")
            img_a = markdown.util.etree.SubElement(tweet, 'a')
            img_a.set("href", url)
            img_a.set("target", "_blank")
            profile_img = markdown.util.etree.SubElement(img_a, 'img')
            profile_img.set('class', 'twitter-avatar')
            # For some reason, for, e.g. tweet 285072525413724161,
            # python-twitter does not give us a
            # profile_image_url_https, but instead puts that URL in
            # profile_image_url. So use _https if available, but fall
            # back gracefully.
            image_url = user.get('profile_image_url_https', user['profile_image_url'])
            profile_img.set('src', image_url)

            text = unescape(res['text'])
            urls = res.get('urls', [])
            user_mentions = res.get('user_mentions', [])
            media = res.get('media', []) # type: List[Dict[text_type, Any]]
            p = self.twitter_text(text, urls, user_mentions, media)
            tweet.append(p)

            span = markdown.util.etree.SubElement(tweet, 'span')
            span.text = u"- %s (@%s)" % (user['name'], user['screen_name'])

            # Add image previews
            for media_item in media:
                # Only photos have a preview image
                if media_item['type'] != 'photo':
                    continue

                # Find the image size that is smaller than
                # TWITTER_MAX_IMAGE_HEIGHT px tall or the smallest
                size_name_tuples = list(media_item['sizes'].items())
                size_name_tuples.sort(reverse=True,
                                      key=lambda x: x[1]['h'])
                for size_name, size in size_name_tuples:
                    if size['h'] < self.TWITTER_MAX_IMAGE_HEIGHT:
                        break

                media_url = u'%s:%s' % (media_item['media_url_https'], size_name)
                img_div = markdown.util.etree.SubElement(tweet, 'div')
                img_div.set('class', 'twitter-image')
                img_a = markdown.util.etree.SubElement(img_div, 'a')
                img_a.set('href', media_item['url'])
                img_a.set('target', '_blank')
                img_a.set('title', media_item['url'])
                img = markdown.util.etree.SubElement(img_a, 'img')
                img.set('src', media_url)

            return tweet
        except:
            # We put this in its own try-except because it requires external
            # connectivity. If Twitter flakes out, we don't want to not-render
            # the entire message; we just want to not show the Twitter preview.
            logging.warning(traceback.format_exc())
            return None

    def run(self, root):
        # type: (Element) -> None
        # Get all URLs from the blob
        found_urls = walk_tree(root, lambda e: e.get("href") if e.tag == "a" else None)

        # If there are more than 5 URLs in the message, don't do inline previews
        if len(found_urls) == 0 or len(found_urls) > 5:
            return

        rendered_tweet_count = 0

        for url in found_urls:
            dropbox_image = self.dropbox_image(url)
            if dropbox_image is not None:
                class_attr = "message_inline_ref"
                is_image = dropbox_image["is_image"]
                if is_image:
                    class_attr = "message_inline_image"
                    # Not making use of title and description of images
                add_a(root, dropbox_image['image'], url,
                      title=dropbox_image.get('title', ""),
                      desc=dropbox_image.get('desc', ""),
                      class_attr=class_attr)
                continue
            if self.is_image(url):
                add_a(root, url, url)
                continue
            if get_tweet_id(url) is not None:
                if rendered_tweet_count >= self.TWITTER_MAX_TO_PREVIEW:
                    # Only render at most one tweet per message
                    continue
                twitter_data = self.twitter_link(url)
                if twitter_data is None:
                    # This link is not actually a tweet known to twitter
                    continue
                rendered_tweet_count += 1
                div = markdown.util.etree.SubElement(root, "div")
                div.set("class", "inline-preview-twitter")
                div.insert(0, twitter_data)
                continue
            youtube = self.youtube_image(url)
            if youtube is not None:
                add_a(root, youtube, url)
                continue

class Avatar(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        # type: (Match[text_type]) -> Optional[Element]
        img = markdown.util.etree.Element('img')
        email_address = match.group('email')
        img.set('class', 'message_body_gravatar')
        img.set('src', '/avatar/%s?s=30' % (email_address,))
        img.set('title', email_address)
        img.set('alt', email_address)
        return img

emoji_tree = os.path.join(settings.STATIC_ROOT, "third", "gemoji", "images", "emoji")
path_to_emoji = os.path.join(emoji_tree, '*.png')
path_to_unicode_emoji = os.path.join(emoji_tree, 'unicode', '*.png')

emoji_list = [os.path.splitext(os.path.basename(fn))[0] for fn in glob.glob(path_to_emoji)]
unicode_emoji_list = [os.path.splitext(os.path.basename(fn))[0] for fn in glob.glob(path_to_unicode_emoji)]


def make_emoji(emoji_name, src, display_string):
    # type: (text_type, text_type, text_type) -> Element
    elt = markdown.util.etree.Element('img')
    elt.set('src', src)
    elt.set('class', 'emoji')
    elt.set("alt", display_string)
    elt.set("title", display_string)
    return elt

class UnicodeEmoji(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        # type: (Match[text_type]) -> Optional[Element]
        orig_syntax = match.group('syntax')
        name = hex(ord(orig_syntax))[2:]
        if name in unicode_emoji_list:
            src = '/static/third/gemoji/images/emoji/unicode/%s.png' % (name)
            return make_emoji(name, src, orig_syntax)
        else:
            return None

class Emoji(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        # type: (Match[text_type]) -> Optional[Element]
        orig_syntax = match.group("syntax")
        name = orig_syntax[1:-1]

        realm_emoji = {} # type: Dict[text_type, Dict[str, text_type]]
        if db_data is not None:
            realm_emoji = db_data['emoji']

        if current_message and name in realm_emoji:
            return make_emoji(name, realm_emoji[name]['display_url'], orig_syntax)
        elif name in emoji_list:
            src = '/static/third/gemoji/images/emoji/%s.png' % (name)
            return make_emoji(name, src, orig_syntax)
        else:
            return None

class StreamSubscribeButton(markdown.inlinepatterns.Pattern):
    # This markdown extension has required javascript in
    # static/js/custom_markdown.js
    def handleMatch(self, match):
        # type: (Match[text_type]) -> Element
        stream_name = match.group('stream_name')
        stream_name = stream_name.replace('\\)', ')').replace('\\\\', '\\')

        span = markdown.util.etree.Element('span')
        span.set('class', 'inline-subscribe')
        span.set('data-stream-name', stream_name)

        button = markdown.util.etree.SubElement(span, 'button')
        button.text = 'Subscribe to ' + stream_name
        button.set('class', 'inline-subscribe-button btn')

        error = markdown.util.etree.SubElement(span, 'span')
        error.set('class', 'inline-subscribe-error')

        return span

class ModalLink(markdown.inlinepatterns.Pattern):
    """
    A pattern that allows including in-app modal links in messages.
    """
    def handleMatch(self, match):
        # type: (Match[text_type]) -> Element
        relative_url = match.group('relative_url')
        text = match.group('text')

        a_tag = markdown.util.etree.Element("a")
        a_tag.set("href", relative_url)
        a_tag.set("title", relative_url)
        a_tag.set("data-toggle", "modal")
        a_tag.text = text

        return a_tag

upload_title_re = re.compile(u"^(https?://[^/]*)?(/user_uploads/\\d+)(/[^/]*)?/[^/]*/(?P<filename>[^/]*)$")
def url_filename(url):
    # type: (text_type) -> text_type
    """Extract the filename if a URL is an uploaded file, or return the original URL"""
    match = upload_title_re.match(url)
    if match:
        return match.group('filename')
    else:
        return url

def fixup_link(link, target_blank=True):
    # type: (markdown.util.etree.Element, bool) -> None
    """Set certain attributes we want on every link."""
    if target_blank:
        link.set('target', '_blank')
    link.set('title',  url_filename(link.get('href')))


def sanitize_url(url):
    # type: (text_type) -> text_type
    """
    Sanitize a url against xss attacks.
    See the docstring on markdown.inlinepatterns.LinkPattern.sanitize_url.
    """
    try:
        parts = urllib.parse.urlparse(url.replace(' ', '%20'))
        scheme, netloc, path, params, query, fragment = parts
    except ValueError:
        # Bad url - so bad it couldn't be parsed.
        return ''

    # If there is no scheme or netloc and there is a '@' in the path,
    # treat it as a mailto: and set the appropriate scheme
    if scheme == '' and netloc == '' and '@' in path:
        scheme = 'mailto'
    elif scheme == '' and netloc == '' and len(path) > 0 and path[0] == '/':
        # Allow domain-relative links
        return urllib.parse.urlunparse(('', '', path, params, query, fragment))
    elif (scheme, netloc, path, params, query) == ('', '', '', '', '') and len(fragment) > 0:
        # Allow fragment links
        return urllib.parse.urlunparse(('', '', '', '', '', fragment))

    # Zulip modification: If scheme is not specified, assume http://
    # We re-enter sanitize_url because netloc etc. need to be re-parsed.
    if not scheme:
        return sanitize_url('http://' + url)

    locless_schemes = ['mailto', 'news']
    if netloc == '' and scheme not in locless_schemes:
        # This fails regardless of anything else.
        # Return immediately to save additional proccessing
        return None

    # Upstream code will accept a URL like javascript://foo because it
    # appears to have a netloc.  Additionally there are plenty of other
    # schemes that do weird things like launch external programs.  To be
    # on the safe side, we whitelist the scheme.
    if scheme not in ('http', 'https', 'ftp', 'mailto'):
        return None

    # Upstream code scans path, parameters, and query for colon characters
    # because
    #
    #    some aliases [for javascript:] will appear to urllib.parse to have
    #    no scheme. On top of that relative links (i.e.: "foo/bar.html")
    #    have no scheme.
    #
    # We already converted an empty scheme to http:// above, so we skip
    # the colon check, which would also forbid a lot of legitimate URLs.

    # Url passes all tests. Return url as-is.
    return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))

def url_to_a(url, text = None):
    # type: (text_type, Optional[text_type]) -> Union[Element, text_type]
    a = markdown.util.etree.Element('a')

    href = sanitize_url(url)
    if href is None:
        # Rejected by sanitize_url; render it as plain text.
        return url
    if text is None:
        text = markdown.util.AtomicString(url)

    a.set('href', href)
    a.text = text
    fixup_link(a, 'mailto:' not in href[:7])
    return a

class AutoLink(markdown.inlinepatterns.Pattern):
    def __init__(self, pattern):
        # type: (text_type) -> None
        markdown.inlinepatterns.Pattern.__init__(self, ' ')

        # HACK: we just had python-markdown compile an empty regex.
        # Now replace with the real regex compiled with the flags we want.

        self.pattern = pattern
        self.compiled_re = re.compile(u"^(.*?)%s(.*?)$" % pattern,
                                      re.DOTALL | re.UNICODE | re.VERBOSE)

    def handleMatch(self, match):
        # type: (Match[text_type]) -> ElementStringNone
        url = match.group('url')
        return url_to_a(url)

class UListProcessor(markdown.blockprocessors.OListProcessor):
    """ Process unordered list blocks.

        Based on markdown.blockprocessors.UListProcessor, but does not accept
        '+' or '-' as a bullet character."""

    TAG = 'ul'
    RE = re.compile(u'^[ ]{0,3}[*][ ]+(.*)')

class BugdownUListPreprocessor(markdown.preprocessors.Preprocessor):
    """ Allows unordered list blocks that come directly after a
        paragraph to be rendered as an unordered list

        Detects paragraphs that have a matching list item that comes
        directly after a line of text, and inserts a newline between
        to satisfy Markdown"""

    LI_RE = re.compile(u'^[ ]{0,3}[*][ ]+(.*)', re.MULTILINE)
    HANGING_ULIST_RE = re.compile(u'^.+\\n([ ]{0,3}[*][ ]+.*)', re.MULTILINE)

    def run(self, lines):
        # type: (List[text_type]) -> List[text_type]
        """ Insert a newline between a paragraph and ulist if missing """
        inserts = 0
        fence = None
        copy = lines[:]
        for i in range(len(lines) - 1):
            # Ignore anything that is inside a fenced code block
            m = FENCE_RE.match(lines[i])
            if not fence and m:
                fence = m.group('fence')
            elif fence and m and fence == m.group('fence'):
                fence = None

            # If we're not in a fenced block and we detect an upcoming list
            #  hanging off a paragraph, add a newline
            if not fence and lines[i] and \
                self.LI_RE.match(lines[i+1]) and not self.LI_RE.match(lines[i]):
                copy.insert(i+inserts+1, '')
                inserts += 1
        return copy

# Based on markdown.inlinepatterns.LinkPattern
class LinkPattern(markdown.inlinepatterns.Pattern):
    """ Return a link element from the given match. """
    def handleMatch(self, m):
        # type: (Match[text_type]) -> Optional[Element]
        href = m.group(9)
        if not href:
            return None

        if href[0] == "<":
            href = href[1:-1]
        href = sanitize_url(self.unescape(href.strip()))
        if href is None:
            return None

        el = markdown.util.etree.Element('a')
        el.text = m.group(2)
        el.set('href', href)
        fixup_link(el, target_blank = (href[:1] != '#'))
        return el

def prepare_realm_pattern(source):
    # type: (text_type) -> text_type
    """ Augment a realm filter so it only matches after start-of-string,
    whitespace, or opening delimiters, won't match if there are word
    characters directly after, and saves what was matched as "name". """
    return r"""(?<![^\s'"\(,:<])(?P<name>""" + source + ')(?!\w)'

# Given a regular expression pattern, linkifies groups that match it
# using the provided format string to construct the URL.
class RealmFilterPattern(markdown.inlinepatterns.Pattern):
    """ Applied a given realm filter to the input """
    def __init__(self, source_pattern, format_string, markdown_instance=None):
        # type: (text_type, text_type, Optional[markdown.Markdown]) -> None
        self.pattern = prepare_realm_pattern(source_pattern)
        self.format_string = format_string
        markdown.inlinepatterns.Pattern.__init__(self, self.pattern, markdown_instance)

    def handleMatch(self, m):
        # type: (Match[text_type]) -> Union[Element, text_type]
        return url_to_a(self.format_string % m.groupdict(),
                        m.group("name"))

class UserMentionPattern(markdown.inlinepatterns.Pattern):
    def find_user_for_mention(self, name):
        # type: (text_type) -> Tuple[bool, Dict[str, Any]]
        if db_data is None:
            return (False, None)

        if mention.user_mention_matches_wildcard(name):
            return (True, None)

        user = db_data['full_names'].get(name.lower(), None)
        if user is None:
            user = db_data['short_names'].get(name.lower(), None)

        return (False, user)

    def handleMatch(self, m):
        # type: (Match[text_type]) -> Optional[Element]
        name = m.group(2) or m.group(3)

        if current_message:
            wildcard, user = self.find_user_for_mention(name)

            if wildcard:
                current_message.mentions_wildcard = True
                email = "*"
            elif user:
                current_message.mentions_user_ids.add(user['id'])
                name = user['full_name']
                email = user['email']
            else:
                # Don't highlight @mentions that don't refer to a valid user
                return None

            el = markdown.util.etree.Element("span")
            el.set('class', 'user-mention')
            el.set('data-user-email', email)
            el.text = "@%s" % (name,)
            return el

class AlertWordsNotificationProcessor(markdown.preprocessors.Preprocessor):
    def run(self, lines):
        # type: (Iterable[text_type]) -> Iterable[text_type]
        if current_message and db_data is not None:
            # We check for a user's custom notifications here, as we want
            # to check for plaintext words that depend on the recipient.
            realm_words = db_data['realm_alert_words']
            content = '\n'.join(lines).lower()

            allowed_before_punctuation = "|".join([r'\s', '^', r'[\(\".,\';\[\*`>]'])
            allowed_after_punctuation = "|".join([r'\s', '$', r'[\)\"\?:.,\';\]!\*`]'])

            for user_id, words in six.iteritems(realm_words):
                for word in words:
                    escaped = re.escape(word.lower())
                    match_re = re.compile(u'(?:%s)%s(?:%s)' %
                                            (allowed_before_punctuation,
                                             escaped,
                                             allowed_after_punctuation))
                    if re.search(match_re, content):
                        current_message.user_ids_with_alert_words.add(user_id)

        return lines

# This prevents realm_filters from running on the content of a
# Markdown link, breaking up the link.  This is a monkey-patch, but it
# might be worth sending a version of this change upstream.
class AtomicLinkPattern(LinkPattern):
    def handleMatch(self, m):
        # type: (Match[text_type]) -> Optional[Element]
        ret = LinkPattern.handleMatch(self, m)
        if ret is None:
            return None
        if not isinstance(ret, six.string_types):
            ret.text = markdown.util.AtomicString(ret.text)
        return ret

class Bugdown(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        # type: (markdown.Markdown, Dict[str, Any]) -> None
        del md.preprocessors['reference']

        for k in ('image_link', 'image_reference', 'automail',
                  'autolink', 'link', 'reference', 'short_reference',
                  'escape', 'strong_em', 'emphasis', 'emphasis2',
                  'linebreak', 'strong'):
            del md.inlinePatterns[k]
        try:
            # linebreak2 was removed upstream in version 3.2.1, so
            # don't throw an error if it is not there
            del md.inlinePatterns['linebreak2']
        except Exception:
            pass

        md.preprocessors.add("custom_text_notifications", AlertWordsNotificationProcessor(md), "_end")

        # Custom bold syntax: **foo** but not __foo__
        md.inlinePatterns.add('strong',
            markdown.inlinepatterns.SimpleTagPattern(r'(\*\*)([^\n]+?)\2', 'strong'),
            '>not_strong')

        for k in ('hashheader', 'setextheader', 'olist', 'ulist'):
            del md.parser.blockprocessors[k]

        md.parser.blockprocessors.add('ulist', UListProcessor(md.parser), '>hr')

        # Note that !gravatar syntax should be deprecated long term.
        md.inlinePatterns.add('avatar', Avatar(r'!avatar\((?P<email>[^)]*)\)'), '>backtick')
        md.inlinePatterns.add('gravatar', Avatar(r'!gravatar\((?P<email>[^)]*)\)'), '>backtick')

        md.inlinePatterns.add('stream_subscribe_button',
            StreamSubscribeButton(r'!_stream_subscribe_button\((?P<stream_name>(?:[^)\\]|\\\)|\\)*)\)'), '>backtick')
        md.inlinePatterns.add(
            'modal_link',
            ModalLink(r'!modal_link\((?P<relative_url>[^)]*), (?P<text>[^)]*)\)'),
            '>backtick')
        md.inlinePatterns.add('usermention', UserMentionPattern(mention.find_mentions), '>backtick')
        md.inlinePatterns.add('emoji', Emoji(r'(?<!\w)(?P<syntax>:[^:\s]+:)(?!\w)'), '_end')
        md.inlinePatterns.add('unicodeemoji', UnicodeEmoji(
            u'(?<!\\w)(?P<syntax>[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\u2700-\u27BF])(?!\\w)'),
            '_end')

        md.inlinePatterns.add('link', AtomicLinkPattern(markdown.inlinepatterns.LINK_RE, md), '>backtick')

        for (pattern, format_string) in self.getConfig("realm_filters"):
            md.inlinePatterns.add('realm_filters/%s' % (pattern,),
                                  RealmFilterPattern(pattern, format_string), '>link')

        # A link starts at a word boundary, and ends at space, punctuation, or end-of-input.
        #
        # We detect a url either by the `https?://` or by building around the TLD.

        # In lieu of having a recursive regex (which python doesn't support) to match
        # arbitrary numbers of nested matching parenthesis, we manually build a regexp that
        # can match up to six
        # The inner_paren_contents chunk matches the innermore non-parenthesis-holding text,
        # and the paren_group matches text with, optionally, a matching set of parens
        inner_paren_contents = r"[^\s()\"]*"
        paren_group = r"""
                        [^\s()\"]*?            # Containing characters that won't end the URL
                        (?: \( %s \)           # and more characters in matched parens
                            [^\s()\"]*?        # followed by more characters
                        )*                     # zero-or-more sets of paired parens
                       """
        nested_paren_chunk = paren_group
        for i in range(6):
            nested_paren_chunk = nested_paren_chunk % (paren_group,)
        nested_paren_chunk = nested_paren_chunk % (inner_paren_contents,)
        tlds = '|'.join(list_of_tlds())
        link_regex = r"""
            (?<![^\s'"\(,:<])    # Start after whitespace or specified chars
                                 # (Double-negative lookbehind to allow start-of-string)
            (?P<url>             # Main group
                (?:(?:           # Domain part
                    https?://[\w.:@-]+?   # If it has a protocol, anything goes.
                   |(?:                   # Or, if not, be more strict to avoid false-positives
                        (?:[\w-]+\.)+     # One or more domain components, separated by dots
                        (?:%s)            # TLDs (filled in via format from tlds-alpha-by-domain.txt)
                    )
                )
                (?:/             # A path, beginning with /
                    %s           # zero-to-6 sets of paired parens
                )?)              # Path is optional
                | (?:[\w.-]+\@[\w.-]+\.[\w]+) # Email is separate, since it can't have a path
            )
            (?=                            # URL must be followed by (not included in group)
                [!:;\?\),\.\'\"\>]*         # Optional punctuation characters
                (?:\Z|\s)                  # followed by whitespace or end of string
            )
            """ % (tlds, nested_paren_chunk)
        md.inlinePatterns.add('autolink', AutoLink(link_regex), '>link')

        md.preprocessors.add('hanging_ulists',
                                 BugdownUListPreprocessor(md),
                                 "_begin")

        md.treeprocessors.add("inline_interesting_links", InlineInterestingLinkProcessor(md, self), "_end")

        if settings.CAMO_URI:
            md.treeprocessors.add("rewrite_to_https", InlineHttpsProcessor(md), "_end")

        if self.getConfig("realm") == "zephyr_mirror":
            # Disable almost all inline patterns for zephyr mirror
            # users' traffic that is mirrored.  Note that
            # inline_interesting_links is a treeprocessor and thus is
            # not removed
            for k in md.inlinePatterns.keys():
                if k not in ["autolink"]:
                    del md.inlinePatterns[k]
            for k in md.treeprocessors.keys():
                if k not in ["inline_interesting_links", "inline", "rewrite_to_https"]:
                    del md.treeprocessors[k]
            for k in md.preprocessors.keys():
                if k not in ["custom_text_notifications"]:
                    del md.preprocessors[k]
            for k in md.parser.blockprocessors.keys():
                if k not in ["paragraph"]:
                    del md.parser.blockprocessors[k]

md_engines = {}
realm_filter_data = {} # type: Dict[text_type, List[Tuple[text_type, text_type]]]

def make_md_engine(key, opts):
    # type: (text_type, Dict[str, Any]) -> None
    md_engines[key] = markdown.Markdown(
        safe_mode     = 'escape',
        output_format = 'html',
        extensions    = ['nl2br',
                         'tables',
                         codehilite.makeExtension(configs=[
                    ('force_linenos', False),
                    ('guess_lang',    False)]),
                         fenced_code.makeExtension(),
                         Bugdown(opts)])

def subject_links(domain, subject):
    # type: (text_type, text_type) -> List[text_type]
    from zerver.models import get_realm, RealmFilter, realm_filters_for_domain
    matches = [] # type: List[text_type]

    realm_filters = realm_filters_for_domain(domain)

    for realm_filter in realm_filters:
        pattern = prepare_realm_pattern(realm_filter[0])
        for m in re.finditer(pattern, subject):
            matches += [realm_filter[1] % m.groupdict()]
    return matches

def make_realm_filters(domain, filters):
    # type: (text_type, List[Tuple[text_type, text_type]]) -> None
    global md_engines, realm_filter_data
    if domain in md_engines:
        del md_engines[domain]
    realm_filter_data[domain] = filters

    # Because of how the Markdown config API works, this has confusing
    # large number of layers of dicts/arrays :(
    make_md_engine(domain, {"realm_filters": [filters, "Realm-specific filters for %s" % (domain,)],
                           "realm": [domain, "Realm name"]})

def maybe_update_realm_filters(domain):
    # type: (Optional[text_type]) -> None
    from zerver.models import realm_filters_for_domain, all_realm_filters

    # If domain is None, load all filters
    if domain is None:
        all_filters = all_realm_filters()
        all_filters['default'] = []
        for domain, filters in six.iteritems(all_filters):
            make_realm_filters(domain, filters)
        # Hack to ensure that getConfig("realm") is right for mirrored Zephyrs
        make_realm_filters("zephyr_mirror", [])
    else:
        realm_filters = realm_filters_for_domain(domain)
        if domain not in realm_filter_data or realm_filter_data[domain] != realm_filters:
            # Data has changed, re-load filters
            make_realm_filters(domain, realm_filters)

maybe_update_realm_filters(domain=None)

# We want to log Markdown parser failures, but shouldn't log the actual input
# message for privacy reasons.  The compromise is to replace all alphanumeric
# characters with 'x'.
#
# We also use repr() to improve reproducibility, and to escape terminal control
# codes, which can do surprisingly nasty things.
_privacy_re = re.compile(u'\\w', flags=re.UNICODE)
def _sanitize_for_log(md):
    # type: (markdown.Markdown) -> text_type
    return repr(_privacy_re.sub('x', md))


# Filters such as UserMentionPattern need a message, but python-markdown
# provides no way to pass extra params through to a pattern. Thus, a global.
current_message = None # type: Optional[Message]

# We avoid doing DB queries in our markdown thread to avoid the overhead of
# opening a new DB connection. These connections tend to live longer than the
# threads themselves, as well.
db_data = None # type: Dict[text_type, Any]

def do_convert(md, realm_domain=None, message=None):
    # type: (markdown.Markdown, Optional[text_type], Optional[Message]) -> Optional[text_type]
    """Convert Markdown to HTML, with Zulip-specific settings and hacks."""
    from zerver.models import get_active_user_dicts_in_realm, UserProfile

    if message:
        maybe_update_realm_filters(message.get_realm().domain)

    if realm_domain in md_engines:
        _md_engine = md_engines[realm_domain]
    else:
        _md_engine = md_engines["default"]
    # Reset the parser; otherwise it will get slower over time.
    _md_engine.reset()

    global current_message
    current_message = message

    # Pre-fetch data from the DB that is used in the bugdown thread
    global db_data
    if message:
        realm_users = get_active_user_dicts_in_realm(message.get_realm())

        db_data = {'realm_alert_words': alert_words.alert_words_in_realm(message.get_realm()),
                   'full_names':        dict((user['full_name'].lower(), user) for user in realm_users),
                   'short_names':       dict((user['short_name'].lower(), user) for user in realm_users),
                   'emoji':             message.get_realm().get_emoji()}

    try:
        # Spend at most 5 seconds rendering.
        # Sometimes Python-Markdown is really slow; see
        # https://trac.zulip.net/ticket/345
        return timeout(5, _md_engine.convert, md)
    except:
        from zerver.lib.actions import internal_send_message

        cleaned = _sanitize_for_log(md)

        # Output error to log as well as sending a zulip and email
        logging.getLogger('').error('Exception in Markdown parser: %sInput (sanitized) was: %s'
            % (traceback.format_exc(), cleaned))
        subject = "Markdown parser failure on %s" % (platform.node(),)
        if settings.ERROR_BOT is not None:
            internal_send_message(settings.ERROR_BOT, "stream",
                    "errors", subject, "Markdown parser failed, email sent with details.")
        mail.mail_admins(subject, "Failed message: %s\n\n%s\n\n" % (
                                    cleaned, traceback.format_exc()),
                         fail_silently=False)
        return None
    finally:
        current_message = None
        db_data = None

bugdown_time_start = 0.0
bugdown_total_time = 0.0
bugdown_total_requests = 0

def get_bugdown_time():
    # type: () -> float
    return bugdown_total_time

def get_bugdown_requests():
    # type: () -> int
    return bugdown_total_requests

def bugdown_stats_start():
    # type: () -> None
    global bugdown_time_start
    bugdown_time_start = time.time()

def bugdown_stats_finish():
    # type: () -> None
    global bugdown_total_time
    global bugdown_total_requests
    global bugdown_time_start
    bugdown_total_requests += 1
    bugdown_total_time += (time.time() - bugdown_time_start)

def convert(md, realm_domain=None, message=None):
    # type: (markdown.Markdown, Optional[text_type], Optional[Message]) -> Optional[text_type]
    bugdown_stats_start()
    ret = do_convert(md, realm_domain, message)
    bugdown_stats_finish()
    return ret
