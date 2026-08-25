import re

from bs4 import Tag
from typing_extensions import override

from zerver.lib.markdown import get_markdown_image_for_url
from zerver.lib.markdown.from_html import ZulipMarkdownConverter, convert_html_to_markdown

# https://learn.microsoft.com/en-us/graph/api/chatmessagehostedcontent-get
HOSTED_CONTENT_GRAPH_API_URL_REGEX = r"https://graph\.microsoft\.com/v1\.0/teams/[^/]+/channels/[^/]+/messages/[^/]+/hostedContents/[^/]+/\$value"
HOSTED_CONTENT_MARKDOWN_IMAGE_SYNTAX_REGEX = rf"""
            !\[
               (?P<file_name>[^\]]+)
            \]\(
               (?P<api_url>{HOSTED_CONTENT_GRAPH_API_URL_REGEX})
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
        if re.fullmatch(HOSTED_CONTENT_GRAPH_API_URL_REGEX, src):
            return get_markdown_image_for_url(alt, src)
        return super().convert_img(el, text, parent_tags)


def convert_microsoft_teams_html_to_markdown(html: str) -> str:
    return convert_html_to_markdown(html, converter_class=MicrosoftTeamsToZulipMarkdownConverter)
