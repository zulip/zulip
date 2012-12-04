import markdown
import logging
import traceback
import urlparse
import re

from zephyr.lib.avatar  import gravatar_hash
from zephyr.lib.bugdown import codehilite, fenced_code

class Gravatar(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        img = markdown.util.etree.Element('img')
        img.set('class', 'message_body_gravatar img-rounded')
        img.set('src', 'https://secure.gravatar.com/avatar/%s?d=identicon&s=30'
            % (gravatar_hash(match.group('email')),))
        return img

class AutoLink(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        url = match.group('url')
        a = markdown.util.etree.Element('a')
        a.set('href', url)
        a.text = url
        return a

class UListProcessor(markdown.blockprocessors.OListProcessor):
    """ Process unordered list blocks.

        Based on markdown.blockprocessors.UListProcessor, but does not accept
        '+' as a bullet character."""

    TAG = 'ul'
    RE = re.compile(r'^[ ]{0,3}[*-][ ]+(.*)')

# Based on markdown.inlinepatterns.LinkPattern
class LinkPattern(markdown.inlinepatterns.Pattern):
    """ Return a link element from the given match. """
    def handleMatch(self, m):
        el = markdown.util.etree.Element("a")
        el.text = m.group(2)
        title = m.group(13)
        href = m.group(9)

        if href:
            if href[0] == "<":
                href = href[1:-1]
            el.set("href", self.sanitize_url(self.unescape(href.strip())))
        else:
            el.set("href", "")

        if title:
            title = markdown.inlinepatterns.dequote(self.unescape(title))
            el.set("title", title)
        return el

    def sanitize_url(self, url):
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

        # Humbug modification: If scheme is not specified, assume http://
        # It's unlikely that users want relative links within humbughq.com.
        # We re-enter sanitize_url because netloc etc. need to be re-parsed.
        if not scheme:
            return self.sanitize_url('http://' + url)

        locless_schemes = ['', 'mailto', 'news']
        if netloc == '' and scheme not in locless_schemes:
            # This fails regardless of anything else.
            # Return immediately to save additional proccessing
            return ''

        for part in parts[2:]:
            if ":" in part:
                # Not a safe url
                return ''

        # Url passes all tests. Return url as-is.
        return urlparse.urlunparse(parts)

class Bugdown(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        for k in ('image_link', 'image_reference', 'automail', 'autolink', 'link'):
            del md.inlinePatterns[k]

        for k in ('hashheader', 'setextheader', 'olist', 'ulist'):
            del md.parser.blockprocessors[k]

        md.parser.blockprocessors.add('ulist', UListProcessor(md.parser), '>hr')

        md.inlinePatterns.add('gravatar', Gravatar(r'!gravatar\((?P<email>[^)]*)\)'), '_begin')
        md.inlinePatterns.add('link', LinkPattern(markdown.inlinepatterns.LINK_RE, md), '>reference')

        # A link starts at a word boundary, and ends at space or end-of-input.
        # But any trailing punctuation (other than /) is not included.
        # We accomplish this with a non-greedy match followed by a greedy
        # lookahead assertion.
        #
        # markdown.inlinepatterns.Pattern compiles this with re.UNICODE, which
        # is important because we're using \w.
        link_regex = r'\b(?P<url>https?://[^\s]+?)(?=[^\w/]*(\s|\Z))'
        md.inlinePatterns.add('autolink', AutoLink(link_regex), '>link')

_md_engine = markdown.Markdown(
    safe_mode     = 'escape',
    output_format = 'html',
    extensions    = ['nl2br',
        codehilite.makeExtension(configs=[
            ('force_linenos', False),
            ('guess_lang',    False)]),
        fenced_code.makeExtension(),
        Bugdown()])

# We want to log Markdown parser failures, but shouldn't log the actual input
# message for privacy reasons.  The compromise is to replace all alphanumeric
# characters with 'x'.
#
# We also use repr() to improve reproducibility, and to escape terminal control
# codes, which can do surprisingly nasty things.
_privacy_re = re.compile(r'\w', flags=re.UNICODE)
def _sanitize_for_log(md):
    return repr(_privacy_re.sub('x', md))

def _linkify(match):
    url = match.group('url')
    return ' [%s](%s) ' % (url, url)

def convert(md):
    """Convert Markdown to HTML, with Humbug-specific settings and hacks."""

    # Reset the parser; otherwise it will get slower over time.
    _md_engine.reset()

    try:
        html = _md_engine.convert(md)
    except:
        # FIXME: Do something more reasonable here!
        html = '<p>[Humbug note: Sorry, we could not understand the formatting of your message]</p>'
        logging.getLogger('').error('Exception in Markdown parser: %sInput (sanitized) was: %s'
            % (traceback.format_exc(), _sanitize_for_log(md)))

    return html
