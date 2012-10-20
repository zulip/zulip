import re
import markdown

from zephyr.lib.avatar import gravatar_hash

class Gravatar(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        # NB: the first match of our regex is match.group(2) due to
        # markdown internal matches
        img = markdown.util.etree.Element('img')
        img.set('class', 'message_body_gravatar img-rounded')
        img.set('src', 'https://secure.gravatar.com/avatar/%s?d=identicon&s=30'
            % (gravatar_hash(match.group(2)),))
        return img

class Bugdown(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        del md.inlinePatterns['image_link']
        del md.inlinePatterns['image_reference']
        del md.parser.blockprocessors['hashheader']
        del md.parser.blockprocessors['setextheader']

        md.inlinePatterns.add('gravatar', Gravatar(r'!gravatar\(([^)]*)\)'), '_begin')

# We need to re-initialize the markdown engine every 30 messages
# due to some sort of performance leak in the markdown library.
MAX_MD_ENGINE_USES = 30

_md_engine = None
_use_count = 0

# A link starts after whitespace, and cannot contain spaces,
# end parentheses, or end brackets (which would confuse Markdown).
# FIXME: Use one of the actual linkification extensions.
_link_regex = re.compile(r'(\s|\A)(?P<url>https?://[^\s\])]+)')

def _linkify(match):
    url = match.group('url')
    return ' [%s](%s) ' % (url, url)

def convert(md):
    """Convert Markdown to HTML, with Humbug-specific settings and hacks."""
    global _md_engine, _use_count

    if _md_engine is None:
        _md_engine = markdown.Markdown(
            extensions    = ['fenced_code', 'codehilite', 'nl2br', Bugdown()],
            safe_mode     = 'escape',
            output_format = 'xhtml')

    md = _link_regex.sub(_linkify, md)

    try:
        html = _md_engine.convert(md)
    except:
        # FIXME: Do something more reasonable here!
        html = '<p>[Humbug note: Sorry, we could not understand the formatting of your message]</p>'

    _use_count += 1
    if _use_count >= MAX_MD_ENGINE_USES:
        _md_engine = None
        _use_count = 0

    return html
