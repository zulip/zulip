import re

from bs4 import Tag
from typing_extensions import override

from zerver.lib.markdown import get_markdown_image_for_url
from zerver.lib.markdown.from_html import ZulipMarkdownConverter, convert_html_to_markdown

# There are different hosted content URL patterns for channels and direct
# messages (chats).
# https://learn.microsoft.com/en-us/graph/api/chatmessagehostedcontent-get
CHANNELS_HOSTED_CONTENT_GRAPH_API_URL_REGEX = r"https://graph\.microsoft\.com/v1\.0/teams/[^/]+/channels/[^/]+/messages/[^/]+/hostedContents/[^/]+/\$value"
CHATS_HOSTED_CONTENT_GRAPH_API_URL_REGEX = (
    r"https://graph\.microsoft\.com/v1\.0/chats/[^/]+/messages/[^/]+/hostedContents/[^/]+/\$value"
)
HOSTED_CONTENT_GRAPH_API_URL_REGEXES = [
    CHANNELS_HOSTED_CONTENT_GRAPH_API_URL_REGEX,
    CHATS_HOSTED_CONTENT_GRAPH_API_URL_REGEX,
]
HOSTED_CONTENT_MARKDOWN_IMAGE_SYNTAX_REGEX = r"""
            !\[
               (?P<file_name>[^\]]+)
            \]\(
               (?P<api_url>{api_url_regex})
            \)
            """


class MicrosoftTeamsToZulipMarkdownConverter(ZulipMarkdownConverter):
    """HTML-to-Markdown converter for Microsoft Teams exports.

    Hosted-content images are kept in inline `![alt](src)` form, which
    process_hosted_content_attachments matches to download each image
    and rewrite it into a Zulip upload link.  Other images get the base
    class's external-link treatment.
    """

    @override
    def convert_img(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        src = el.get("src", "")
        alt = el.get("alt", "")
        assert isinstance(src, str)
        assert isinstance(alt, str)
        if any(re.fullmatch(pattern, src) for pattern in HOSTED_CONTENT_GRAPH_API_URL_REGEXES):
            return get_markdown_image_for_url(alt, src)
        return super().convert_img(el, text, parent_tags)


def convert_microsoft_teams_html_to_markdown(html: str) -> str:
    return convert_html_to_markdown(html, converter_class=MicrosoftTeamsToZulipMarkdownConverter)
