import re
import markdown
import logging
import traceback

from zephyr.lib.avatar  import gravatar_hash
from zephyr.lib.bugdown import codehilite

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

class Bugdown(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        for k in ('image_link', 'image_reference', 'automail', 'autolink'):
            del md.inlinePatterns[k]

        for k in ('hashheader', 'setextheader'):
            del md.parser.blockprocessors[k]

        md.inlinePatterns.add('gravatar', Gravatar(r'!gravatar\((?P<email>[^)]*)\)'), '_begin')

        # A link starts after whitespace and continues to the next whitespace.
        link_regex = r'\b(?P<url>https?://[^\s[\](){}<>]+)'
        md.inlinePatterns.add('autolink', AutoLink(link_regex), '_begin')

# We need to re-initialize the markdown engine every 30 messages
# due to some sort of performance leak in the markdown library.
MAX_MD_ENGINE_USES = 30

_md_engine = None
_use_count = 0

def _linkify(match):
    url = match.group('url')
    return ' [%s](%s) ' % (url, url)

def convert(md):
    """Convert Markdown to HTML, with Humbug-specific settings and hacks."""
    global _md_engine, _use_count

    if _md_engine is None:
        _md_engine = markdown.Markdown(
            safe_mode     = 'escape',
            output_format = 'xhtml',
            extensions    = ['fenced_code', 'nl2br',
                codehilite.makeExtension(configs=[('force_linenos', False)]),
                Bugdown()])

    try:
        html = _md_engine.convert(md)
    except:
        # FIXME: Do something more reasonable here!
        #
        # NB: For security, we must not print the bare Markdown input.
        # It could contain terminal control codes, which can do
        # surprisingly nasty things.

        html = '<p>[Humbug note: Sorry, we could not understand the formatting of your message]</p>'
        logging.getLogger('').error('Exception in Markdown parser: %sInput was: %s'
            % (traceback.format_exc(), repr(md)))

    _use_count += 1
    if _use_count >= MAX_MD_ENGINE_USES:
        _md_engine = None
        _use_count = 0

    return html
