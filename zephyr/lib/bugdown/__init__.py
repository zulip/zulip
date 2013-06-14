import markdown
import logging
import traceback
import urlparse
import re
import os.path
import glob
import urllib2
import itertools
import simplejson
import twitter
import platform
import time

import httplib2

from hashlib import sha1

from django.core import mail
from django.conf import settings

from zephyr.lib.avatar  import gravatar_hash
from zephyr.lib.bugdown import codehilite, fenced_code
from zephyr.lib.bugdown.fenced_code import FENCE_RE
from zephyr.lib.timeout import timeout, TimeoutExpired
from zephyr.lib.cache import cache_with_key, cache_get_many, cache_set_many
from embedly import Embedly

embedly_client = Embedly(settings.EMBEDLY_KEY, timeout=2.5)

# Format version of the bugdown rendering; stored along with rendered
# messages so that we can efficiently determine what needs to be re-rendered
version = 1

def list_of_tlds():
    # HACK we manually blacklist .py
    blacklist = ['PY\n', ]

    # tlds-alpha-by-domain.txt comes from http://data.iana.org/TLD/tlds-alpha-by-domain.txt
    tlds_file = os.path.join(os.path.dirname(__file__), 'tlds-alpha-by-domain.txt')
    tlds = [tld.lower().strip() for tld in open(tlds_file, 'r')
                if not tld in blacklist and not tld[0].startswith('#')]
    tlds.sort(key=len, reverse=True)
    return tlds

def walk_tree(root, processor, stop_after_first=False):
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

def add_a(root, url, link, height=None):
    div = markdown.util.etree.SubElement(root, "div")
    div.set("class", "message_inline_image");
    a = markdown.util.etree.SubElement(div, "a")
    a.set("href", link)
    a.set("target", "_blank")
    a.set("title", link)
    img = markdown.util.etree.SubElement(a, "img")
    img.set("src", url)

def hash_embedly_url(link):
    return 'embedly:' + sha1(link).hexdigest()

@cache_with_key(lambda tweet_id: tweet_id, cache_name="database", with_statsd_key="tweet_data")
def fetch_tweet_data(tweet_id):
    if settings.TEST_SUITE:
        import testing_mocks
        res = testing_mocks.twitter(tweet_id)
    else:
        if settings.STAGING_DEPLOYED or settings.TESTING_DEPLOYED:
            # Application: "Humbug HQ"
            api = twitter.Api(consumer_key = 'xxxxxxxxxxxxxxxxxxxxxx',
                              consumer_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                              access_token_key = 'xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                              access_token_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
        elif settings.DEPLOYED:
            # This is the real set of API credentials used by our real server,
            # and we probably shouldn't test with it just so we don't waste its requests
            # Application: "Humbug HQ - Production"
            api = twitter.Api(consumer_key = 'xxxxxxxxxxxxxxxxxxxxx',
                              consumer_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                              access_token_key = 'xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                              access_token_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
        else:
            # Application: "Humbug HQ Test"
            api = twitter.Api(consumer_key = 'xxxxxxxxxxxxxxxxxxxxxx',
                              consumer_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                              access_token_key = 'xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                              access_token_secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
        try:
            # Sometimes Twitter hangs on responses.  Timing out here
            # will cause the Tweet to go through as-is with no inline
            # preview, rather than having the message be rejected
            # entirely. This timeout needs to be less than our overall
            # formatting timeout.
            res = timeout(3, api.GetStatus, tweet_id).AsDict()
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

def get_tweet_id(url):
    parsed_url = urlparse.urlparse(url)
    if not (parsed_url.netloc == 'twitter.com' or parsed_url.netloc.endswith('.twitter.com')):
        return False

    tweet_id_match = re.match(r'^/.*?/status(es)?/(?P<tweetid>\d{18})$', parsed_url.path)
    if not tweet_id_match:
        return False
    return tweet_id_match.group("tweetid")


class InlineInterestingLinkProcessor(markdown.treeprocessors.Treeprocessor):
    def is_image(self, url):
        parsed_url = urlparse.urlparse(url)
        # List from http://support.google.com/chromeos/bin/answer.py?hl=en&answer=183093
        for ext in [".bmp", ".gif", ".jpg", "jpeg", ".png", ".webp"]:
            if parsed_url.path.lower().endswith(ext):
                return True
        return False

    def dropbox_image(self, url):
        if not self.is_image(url):
            return None
        parsed_url = urlparse.urlparse(url)
        if (parsed_url.netloc == 'dropbox.com' or parsed_url.netloc.endswith('.dropbox.com')) \
                and (parsed_url.path.startswith('/s/') or parsed_url.path.startswith('/sh/')):
            return "%s?dl=1" % (url,)
        return None

    def youtube_image(self, url):
        # Youtube video id extraction regular expression from http://pastebin.com/KyKAFv1s
        # If it matches, match.group(2) is the video id.
        youtube_re = r'^((?:https?://)?(?:youtu\.be/|(?:\w+\.)?youtube(?:-nocookie)?\.com/)(?:(?:(?:v|embed)/)|(?:(?:watch(?:_popup)?(?:\.php)?)?(?:\?|#!?)(?:.+&)?v=)))?([0-9A-Za-z_-]+)(?(1).+)?$'
        match = re.match(youtube_re, url)
        if match is None:
            return None
        return "http://i.ytimg.com/vi/%s/default.jpg" % (match.group(2),)

    def twitter_link(self, url):
        tweet_id = get_tweet_id(url)

        if not tweet_id:
            return None

        try:
            res = fetch_tweet_data(tweet_id)
            if res is None:
                return None
            user = res['user']
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
            p = markdown.util.etree.SubElement(tweet, 'p')
            p.text = res['text']
            span = markdown.util.etree.SubElement(tweet, 'span')
            span.text = "- %s (@%s)" % (user['name'], user['screen_name'])

            return tweet
        except:
            # We put this in its own try-except because it requires external
            # connectivity. If Twitter flakes out, we don't want to not-render
            # the entire message; we just want to not show the Twitter preview.
            logging.warning(traceback.format_exc())
            return None

    def do_embedly(self, root, supported_urls):
        # embed.ly support disabled on prod/staging until it can be
        # properly debugged.
        #
        # We're not deleting the code for now, since we expect to
        # restore it and want to be able to update it along with
        # future refactorings rather than keeping it as a separate
        # branch.
        if settings.DEPLOYED:
            return

        # We want this to be able to easily reverse the hashing later
        keys_to_links = dict((hash_embedly_url(link), link) for link in supported_urls)
        cache_hits = cache_get_many(keys_to_links.keys(), cache_name="database")

        # Construct a dict of url => oembed_data pairs
        oembeds = dict((keys_to_links[key], cache_hits[key]) for key in cache_hits)

        to_process = [url for url in supported_urls if not url in oembeds]
        to_cache = {}

        if to_process:
            # Don't touch embed.ly if we have everything cached.
            try:
                responses = embedly_client.oembed(to_process, maxwidth=250)
            except httplib2.socket.timeout:
                # We put this in its own try-except because it requires external
                # connectivity. If embedly flakes out, we don't want to not-render
                # the entire message; we just want to not show the embedly preview.
                logging.warning("Embedly Embed timeout for URLs: %s" % (" ".join(to_process)))
                logging.warning(traceback.format_exc())
                return root
            except Exception:
                # If things break for any other reason, don't make things sad.
                logging.warning(traceback.format_exc())
                return root
            for oembed_data in responses:
                # Don't cache permanent errors
                if oembed_data["type"] == "error" and \
                        oembed_data["error_code"] in (500, 501, 503):
                    continue
                # Convert to dict because otherwise pickling won't work.
                to_cache[oembed_data["original_url"]] = dict(oembed_data)

            # Cache the newly collected data to the database
            cache_set_many(dict((hash_embedly_url(link), to_cache[link]) for link in to_cache),
                           cache_name="database")
            oembeds.update(to_cache)

        # Now let's process the URLs in order
        for link in supported_urls:
            oembed_data = oembeds[link]

            if oembed_data["type"] in ("link"):
                continue
            elif oembed_data["type"] in ("video", "rich") and "script" not in oembed_data["html"]:
                placeholder = self.markdown.htmlStash.store(oembed_data["html"], safe=True)
                el = markdown.util.etree.SubElement(root, "p")
                el.text = placeholder
            else:
                try:
                    add_a(root,
                          oembed_data["thumbnail_url"],
                          link,
                          height=oembed_data["thumbnail_height"])
                except KeyError:
                    # We didn't have a thumbnail, so let's just bail and keep on going...
                    continue
        return root

    def run(self, root):
        # Get all URLs from the blob
        found_urls = walk_tree(root, lambda e: e.get("href") if e.tag == "a" else None)

        # If there are more than 5 URLs in the message, don't do inline previews
        if len(found_urls) == 0 or len(found_urls) > 5:
            return

        rendered_tweet = False
        embedly_urls = []
        for url in found_urls:
            dropbox = self.dropbox_image(url)
            if dropbox is not None:
                add_a(root, dropbox, url)
                continue
            if self.is_image(url):
                add_a(root, url, url)
                continue
            if get_tweet_id(url):
                if rendered_tweet:
                    # Only render at most one tweet per message
                    continue
                twitter_data = self.twitter_link(url)
                if twitter_data is None:
                    # This link is not actually a tweet known to twitter
                    continue
                rendered_tweet = True
                div = markdown.util.etree.SubElement(root, "div")
                div.set("class", "inline-preview-twitter")
                div.insert(0, twitter_data)
                continue
            if embedly_client.is_supported(url):
                embedly_urls.append(url)
                continue
            # NOTE: The youtube code below is inactive at least on
            # staging because embedy.ly is currently handling those
            youtube = self.youtube_image(url)
            if youtube is not None:
                add_a(root, youtube, url)
                continue

        self.do_embedly(root, embedly_urls)

class Gravatar(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        img = markdown.util.etree.Element('img')
        img.set('class', 'message_body_gravatar img-rounded')
        img.set('src', 'https://secure.gravatar.com/avatar/%s?d=identicon&s=30'
            % (gravatar_hash(match.group('email')),))
        return img

path_to_emoji = os.path.join(os.path.dirname(__file__), '..', '..',
                             # This should be zephyr/
                             'static', 'third', 'gemoji', 'images', 'emoji', '*.png')
emoji_list = [os.path.splitext(os.path.basename(fn))[0] for fn in glob.glob(path_to_emoji)]

def make_emoji(emoji_name, display_string):
    elt = markdown.util.etree.Element('img')
    elt.set('src', 'static/third/gemoji/images/emoji/%s.png' % (emoji_name,))
    elt.set('class', 'emoji')
    elt.set("alt", display_string)
    elt.set("title", display_string)
    return elt

class Emoji(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        orig_syntax = match.group("syntax")
        name = orig_syntax[1:-1]
        if name not in emoji_list:
            return orig_syntax
        return make_emoji(name, orig_syntax)

def fixup_link(link, target_blank=True):
    """Set certain attributes we want on every link."""
    if target_blank:
        link.set('target', '_blank')
    link.set('title',  link.get('href'))


def sanitize_url(url):
    """
    Sanitize a url against xss attacks.
    See the docstring on markdown.inlinepatterns.LinkPattern.sanitize_url.
    """
    try:
        parts = urlparse.urlparse(url.replace(' ', '%20'))
        scheme, netloc, path, params, query, fragment = parts
    except ValueError:
        # Bad url - so bad it couldn't be parsed.
        return ''

    # If there is no scheme or netloc and there is a '@' in the path,
    # treat it as a mailto: and set the appropriate scheme
    if scheme == '' and netloc == '' and '@' in path:
        scheme = 'mailto'

    # Humbug modification: If scheme is not specified, assume http://
    # It's unlikely that users want relative links within humbughq.com.
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
    #    some aliases [for javascript:] will appear to urlparse() to have
    #    no scheme. On top of that relative links (i.e.: "foo/bar.html")
    #    have no scheme.
    #
    # We already converted an empty scheme to http:// above, so we skip
    # the colon check, which would also forbid a lot of legitimate URLs.

    # Url passes all tests. Return url as-is.
    return urlparse.urlunparse((scheme, netloc, path, params, query, fragment))

def url_to_a(url, text = None):
    a = markdown.util.etree.Element('a')

    href = sanitize_url(url)
    if href is None:
        # Rejected by sanitize_url; render it as plain text.
        return url
    if text is None:
        text = url

    a.set('href', href)
    a.text = text
    fixup_link(a, not 'mailto:' in href[:7])
    return a

class AutoLink(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        url = match.group('url')
        # As this will also match already-matched https?:// links,
        # don't doubly-link them
        if url[:5] == 'http:' or url[:6] == 'https:':
            return url
        return url_to_a(url)

class HttpLink(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        url = match.group('url')
        return url_to_a(url)

class UListProcessor(markdown.blockprocessors.OListProcessor):
    """ Process unordered list blocks.

        Based on markdown.blockprocessors.UListProcessor, but does not accept
        '+' or '-' as a bullet character."""

    TAG = 'ul'
    RE = re.compile(r'^[ ]{0,3}[*][ ]+(.*)')

class BugdownUListPreprocessor(markdown.preprocessors.Preprocessor):
    """ Allows unordered list blocks that come directly after a
        paragraph to be rendered as an unordered list

        Detects paragraphs that have a matching list item that comes
        directly after a line of text, and inserts a newline between
        to satisfy Markdown"""

    LI_RE = re.compile(r'^[ ]{0,3}[*][ ]+(.*)', re.MULTILINE)
    HANGING_ULIST_RE = re.compile(r'^.+\n([ ]{0,3}[*][ ]+.*)', re.MULTILINE)

    def run(self, lines):
        """ Insert a newline between a paragraph and ulist if missing """
        inserts = 0
        fence = None
        copy = lines[:]
        for i in xrange(len(lines) - 1):
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
        # Return the original link syntax as plain text,
        # if the link fails checks.
        orig_syntax = m.group(0)

        href = m.group(9)
        if not href:
            return orig_syntax

        if href[0] == "<":
            href = href[1:-1]
        href = sanitize_url(self.unescape(href.strip()))
        if href is None:
            return orig_syntax

        el = markdown.util.etree.Element('a')
        el.text = m.group(2)
        el.set('href', href)
        fixup_link(el)
        return el

# Given a regular expression pattern, linkifies groups that match it
# using the provided format string to construct the URL.
class RealmFilterPattern(markdown.inlinepatterns.Pattern):
    """ Applied a given realm filter to the input """
    def __init__(self, source_pattern, format_string, markdown_instance=None):
        self.pattern = r'\b(?P<name>' + source_pattern + ')(?!\w)'
        self.format_string = format_string
        markdown.inlinepatterns.Pattern.__init__(self, self.pattern, markdown_instance)

    def handleMatch(self, m):
        return url_to_a(self.format_string % m.groupdict(),
                        m.group("name"))

class Bugdown(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        del md.preprocessors['reference']

        for k in ('image_link', 'image_reference', 'automail',
                  'autolink', 'link', 'reference', 'short_reference',
                  'escape', 'strong_em', 'emphasis', 'emphasis2',
                  'strong'):
            del md.inlinePatterns[k]

        # Custom bold syntax: **foo** but not __foo__
        md.inlinePatterns.add('strong',
            markdown.inlinepatterns.SimpleTagPattern(r'(\*\*)([^\n]+?)\2', 'strong'),
            '>not_strong')

        for k in ('hashheader', 'setextheader', 'olist', 'ulist'):
            del md.parser.blockprocessors[k]

        md.parser.blockprocessors.add('ulist', UListProcessor(md.parser), '>hr')

        md.inlinePatterns.add('gravatar', Gravatar(r'!gravatar\((?P<email>[^)]*)\)'), '_begin')
        md.inlinePatterns.add('emoji', Emoji(r'(?<!\S)(?P<syntax>:[^:\s]+:)(?!\S)'), '_begin')
        md.inlinePatterns.add('link', LinkPattern(markdown.inlinepatterns.LINK_RE, md), '>backtick')

        # markdown.inlinepatterns.Pattern compiles this with re.UNICODE, which
        # is important because we're using \w.
        #
        # This rule must come after the built-in 'link' markdown linkifier to
        # avoid errors.
        #
        # We support up to 1 nested pair of paranthesis in a url
        http_link_regex = r'\b(?P<url>https?://(?:(?:[^\s]+\([^\s)]+?\)[^\s]*?)|[^\s]+?))(?=[^\w/]*(\s|\Z))'

        md.inlinePatterns.add('http_autolink', HttpLink(http_link_regex), '>link')

        for (pattern, format_string) in self.getConfig("realm_filters"):
            md.inlinePatterns.add('realm_filters/%s' % (pattern,),
                                  RealmFilterPattern(pattern, format_string), '_begin')

        # A link starts at a word boundary, and ends at space, punctuation, or end-of-input.
        #
        # We detect a url by checking for the TLD, and building around it.
        #
        # To support () in urls but not match ending ) when a url is inside a parenthesis,
        # we match at maximum one set of matching parens in a url. We could extend this
        # to match two parenthetical groups, at the cost of more regex complexity.
        #
        # This rule must come after the http_autolink rule we add above to avoid double
        # linkifying.
        tlds = '|'.join(list_of_tlds())
        link_regex = r"\b(?P<url>[^\s]+\.(%s)(?:/[^\s()\":]*?|(/[^\s()\":]*\([^\s()\":]*\)[^\s()\":]*))?)(?=([:;\?\),\.\'\"]\Z|[:;\?\),\.\'\"]\s|\Z|\s))" % (tlds,)
        md.inlinePatterns.add('autolink', AutoLink(link_regex), '>http_autolink')

        md.preprocessors.add('hanging_ulists',
                                 BugdownUListPreprocessor(md),
                                 "_begin")

        md.treeprocessors.add("inline_interesting_links", InlineInterestingLinkProcessor(md), "_end")


md_engines = {}

def make_md_engine(key, opts):
    md_engines[key] = markdown.Markdown(
        safe_mode     = 'escape',
        output_format = 'html',
        extensions    = ['nl2br',
                         codehilite.makeExtension(configs=[
                    ('force_linenos', False),
                    ('guess_lang',    False)]),
                         fenced_code.makeExtension(),
                         Bugdown(opts)])

realm_filters = {
    "default": [],
    "humbughq.com": [
        ("[tT]rac #(?P<id>[0-9]{1,8})", "https://trac.humbughq.com/ticket/%(id)s"),
        ],
    }

for realm in realm_filters.keys():
    # Because of how the Markdown config API works, this has confusing
    # large number of layers of dicts/arrays :(
    make_md_engine(realm, {"realm_filters": [realm_filters[realm], "Realm-specific filters for %s" % (realm,)]})

# We want to log Markdown parser failures, but shouldn't log the actual input
# message for privacy reasons.  The compromise is to replace all alphanumeric
# characters with 'x'.
#
# We also use repr() to improve reproducibility, and to escape terminal control
# codes, which can do surprisingly nasty things.
_privacy_re = re.compile(r'\w', flags=re.UNICODE)
def _sanitize_for_log(md):
    return repr(_privacy_re.sub('x', md))

def do_convert(md, realm):
    """Convert Markdown to HTML, with Humbug-specific settings and hacks."""

    if realm in md_engines:
        _md_engine = md_engines[realm]
    else:
        _md_engine = md_engines["default"]
    # Reset the parser; otherwise it will get slower over time.
    _md_engine.reset()

    try:
        # Spend at most 5 seconds rendering.
        # Sometimes Python-Markdown is really slow; see
        # https://trac.humbughq.com/ticket/345
        return timeout(5, _md_engine.convert, md)
    except:
        from zephyr.models import Recipient
        from zephyr.lib.actions import internal_send_message

        cleaned = _sanitize_for_log(md)

        # Output error to log as well as sending a humbug and email
        logging.getLogger('').error('Exception in Markdown parser: %sInput (sanitized) was: %s'
            % (traceback.format_exc(), cleaned))
        subject = "Markdown parser failure on %s" % (platform.node(),)
        internal_send_message("humbug+errors@humbughq.com", "stream",
                "errors", subject, "Markdown parser failed, email sent with details.")
        mail.mail_admins(subject, "Failed message: %s\n\n%s\n\n" % (
                                    cleaned, traceback.format_exc()),
                         fail_silently=False)
        return None


bugdown_time_start = 0
bugdown_total_time = 0
bugdown_total_requests = 0

def get_bugdown_time():
    return bugdown_total_time

def get_bugdown_requests():
    return bugdown_total_requests

def bugdown_stats_start():
    global bugdown_time_start
    bugdown_time_start = time.time()

def bugdown_stats_finish():
    global bugdown_total_time
    global bugdown_total_requests
    global bugdown_time_start
    bugdown_total_requests += 1
    bugdown_total_time += (time.time() - bugdown_time_start)

def convert(md, realm):
    bugdown_stats_start()
    ret = do_convert(md, realm)
    bugdown_stats_finish()
    return ret
