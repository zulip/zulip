import logging
import re
from html2text import HTML2Text

logger = logging.getLogger(__name__)

_MARKED_SECTION_RE = re.compile(r"<!\[[\s\S]*?\]>", flags=re.IGNORECASE)

def _strip_marked_sections(html: str) -> str:
    """
    Remove XML/HTML marked sections of the form: <![ ... ]> including CDATA and any weird tokens.
    This prevents html.parser.parse_marked_section AssertionError on malformed markers.
    """
    if "<![" not in html:
        return html
    return _MARKED_SECTION_RE.sub("", html)


def convert_html_to_markdown(html: str) -> str:
    """
    Convert HTML string to markdown/text using html2text, but first sanitize
    and guard against html.parser AssertionErrors raised on weird marked sections.
    """
    if not html:
        return ""

    # 1) Remove problematic marked sections like <![CDATA[...]]> or malformed variants.
    sanitized = _strip_marked_sections(html)

    # 2) Use html2text with a defensive try/except that catches AssertionError
    try:
        h = HTML2Text()
        # keep defaults used by your project; example settings:
        h.body_width = 0
        h.single_line_break = True
        return h.handle(sanitized)
    except AssertionError:
        # html.parser raises AssertionError on malformed marked sections; log and fallback.
        logger.warning("Error converting HTML to text (malformed marked section).", exc_info=True)
        # Fallback: return sanitized raw text with tags stripped crudely (or empty string).
        # We prefer to keep something rather than crash tests: strip tags quickly:
        text_fallback = re.sub(r"<[^>]+>", "", sanitized)
        return text_fallback
    except Exception:
        # any other html2text errors
        logger.exception("Unexpected error converting HTML to text")
        return ""
