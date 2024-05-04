# Zulip's main Markdown implementation.  See docs/subsystems/markdown.md for
# detailed documentation on our Markdown syntax.
import cgi
import html
import logging
import mimetypes
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Match,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
    cast,
)
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree.ElementTree import Element, SubElement

import ahocorasick
import dateutil.parser
import dateutil.tz
import lxml.etree
import markdown
import markdown.blockprocessors
import markdown.inlinepatterns
import markdown.postprocessors
import markdown.preprocessors
import markdown.treeprocessors
import markdown.util
import re2
import regex
import requests
import uri_template
from django.conf import settings
from markdown.blockparser import BlockParser
from markdown.extensions import codehilite, nl2br, sane_lists, tables
from tlds import tld_set
from typing_extensions import Self, TypeAlias, override

from zerver.lib import mention
from zerver.lib.cache import cache_with_key
from zerver.lib.camo import get_camo_url
from zerver.lib.emoji import EMOTICON_RE, codepoint_to_name, name_to_codepoint, translate_emoticons
from zerver.lib.emoji_utils import emoji_to_hex_codepoint, unqualify_emoji
from zerver.lib.exceptions import MarkdownRenderingError
from zerver.lib.markdown import fenced_code
from zerver.lib.markdown.fenced_code import FENCE_RE
from zerver.lib.mention import (
    BEFORE_MENTION_ALLOWED_REGEX,
    FullNameInfo,
    MentionBackend,
    MentionData,
)
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.subdomains import is_static_or_current_realm_url
from zerver.lib.tex import render_tex
from zerver.lib.thumbnail import user_uploads_or_external
from zerver.lib.timeout import unsafe_timeout
from zerver.lib.timezone import common_timezones
from zerver.lib.types import LinkifierDict
from zerver.lib.url_encoding import encode_stream, hash_util_encode
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData
from zerver.models import Message, Realm
from zerver.models.linkifiers import linkifiers_for_realm
from zerver.models.realm_emoji import EmojiInfo, get_name_keyed_dict_for_active_realm_emoji

ReturnT = TypeVar("ReturnT")


# Taken from
# https://html.spec.whatwg.org/multipage/system-state.html#safelisted-scheme
html_safelisted_schemes = (
    "bitcoin",
    "geo",
    "im",
    "irc",
    "ircs",
    "magnet",
    "mailto",
    "matrix",
    "mms",
    "news",
    "nntp",
    "openpgp4fpr",
    "sip",
    "sms",
    "smsto",
    "ssh",
    "tel",
    "urn",
    "webcal",
    "wtai",
    "xmpp",
)
allowed_schemes = ("http", "https", "ftp", "file", *html_safelisted_schemes)


class LinkInfo(TypedDict):
    parent: Element
    title: Optional[str]
    index: Optional[int]
    remove: Optional[Element]


@dataclass
class MessageRenderingResult:
    rendered_content: str
    mentions_topic_wildcard: bool
    mentions_stream_wildcard: bool
    mentions_user_ids: Set[int]
    mentions_user_group_ids: Set[int]
    alert_words: Set[str]
    links_for_preview: Set[str]
    user_ids_with_alert_words: Set[int]
    potential_attachment_path_ids: List[str]


@dataclass
class DbData:
    mention_data: MentionData
    realm_uri: str
    realm_alert_words_automaton: Optional[ahocorasick.Automaton]
    active_realm_emoji: Dict[str, EmojiInfo]
    sent_by_bot: bool
    stream_names: Dict[str, int]
    translate_emoticons: bool


# Format version of the Markdown rendering; stored along with rendered
# messages so that we can efficiently determine what needs to be re-rendered
version = 1

_T = TypeVar("_T")
ElementStringNone: TypeAlias = Union[Element, Optional[str]]

EMOJI_REGEX = r"(?P<syntax>:[\w\-\+]+:)"


def verbose_compile(pattern: str) -> Pattern[str]:
    return re.compile(
        rf"^(.*?){pattern}(.*?)$",
        re.DOTALL | re.VERBOSE,
    )


STREAM_LINK_REGEX = rf"""
                     {BEFORE_MENTION_ALLOWED_REGEX} # Start after whitespace or specified chars
                     \#\*\*                         # and after hash sign followed by double asterisks
                         (?P<stream_name>[^\*]+)    # stream name can contain anything
                     \*\*                           # ends by double asterisks
                    """


@lru_cache(None)
def get_compiled_stream_link_regex() -> Pattern[str]:
    # Not using verbose_compile as it adds ^(.*?) and
    # (.*?)$ which cause extra overhead of matching
    # pattern which is not required.
    # With new InlineProcessor these extra patterns
    # are not required.
    return re.compile(
        STREAM_LINK_REGEX,
        re.DOTALL | re.VERBOSE,
    )


STREAM_TOPIC_LINK_REGEX = rf"""
                     {BEFORE_MENTION_ALLOWED_REGEX}  # Start after whitespace or specified chars
                     \#\*\*                          # and after hash sign followed by double asterisks
                         (?P<stream_name>[^\*>]+)    # stream name can contain anything except >
                         >                           # > acts as separator
                         (?P<topic_name>[^\*]+)      # topic name can contain anything
                     \*\*                            # ends by double asterisks
                   """


@lru_cache(None)
def get_compiled_stream_topic_link_regex() -> Pattern[str]:
    # Not using verbose_compile as it adds ^(.*?) and
    # (.*?)$ which cause extra overhead of matching
    # pattern which is not required.
    # With new InlineProcessor these extra patterns
    # are not required.
    return re.compile(
        STREAM_TOPIC_LINK_REGEX,
        re.DOTALL | re.VERBOSE,
    )


@lru_cache(None)
def get_web_link_regex() -> Pattern[str]:
    # We create this one time, but not at startup.  So the
    # first message rendered in any process will have some
    # extra costs.  It's roughly 75ms to run this code, so
    # caching the value is super important here.

    tlds = r"|".join(list_of_tlds())

    # A link starts at a word boundary, and ends at space, punctuation, or end-of-input.
    #
    # We detect a URL either by the `https?://` or by building around the TLD.

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

    file_links = r"| (?:file://(/[^/ ]*)+/?)" if settings.ENABLE_FILE_LINKS else r""
    REGEX = rf"""
        (?<![^\s'"\(,:<])    # Start after whitespace or specified chars
                             # (Double-negative lookbehind to allow start-of-string)
        (?P<url>             # Main group
            (?:(?:           # Domain part
                https?://[\w.:@-]+?   # If it has a protocol, anything goes.
               |(?:                   # Or, if not, be more strict to avoid false-positives
                    (?:[\w-]+\.)+     # One or more domain components, separated by dots
                    (?:{tlds})        # TLDs
                )
            )
            (?:/             # A path, beginning with /
                {nested_paren_chunk}           # zero-to-6 sets of paired parens
            )?)              # Path is optional
            | (?:[\w.-]+\@[\w.-]+\.[\w]+) # Email is separate, since it can't have a path
            {file_links}               # File path start with file:///, enable by setting ENABLE_FILE_LINKS=True
            | (?:bitcoin:[13][a-km-zA-HJ-NP-Z1-9]{{25,34}})  # Bitcoin address pattern, see https://mokagio.github.io/tech-journal/2014/11/21/regex-bitcoin.html
        )
        (?=                            # URL must be followed by (not included in group)
            [!:;\?\),\.\'\"\>]*         # Optional punctuation characters
            (?:\Z|\s)                  # followed by whitespace or end of string
        )
        """
    return verbose_compile(REGEX)


def clear_state_for_testing() -> None:
    # The link regex never changes in production, but our tests
    # try out both sides of ENABLE_FILE_LINKS, so we need
    # a way to clear it.
    get_web_link_regex.cache_clear()


markdown_logger = logging.getLogger()


def rewrite_local_links_to_relative(db_data: Optional[DbData], link: str) -> str:
    """If the link points to a local destination (e.g. #narrow/...),
    generate a relative link that will open it in the current window.
    """

    if db_data:
        realm_uri_prefix = db_data.realm_uri + "/"
        if link.startswith((realm_uri_prefix + "#", realm_uri_prefix + "user_uploads/")):
            return link[len(realm_uri_prefix) :]

    return link


def url_embed_preview_enabled(
    message: Optional[Message] = None, realm: Optional[Realm] = None, no_previews: bool = False
) -> bool:
    if not settings.INLINE_URL_EMBED_PREVIEW:
        return False

    if no_previews:
        return False

    if realm is None and message is not None:
        realm = message.get_realm()

    if realm is None:
        # realm can be None for odd use cases
        # like generating documentation or running
        # test code
        return True

    return realm.inline_url_embed_preview


def image_preview_enabled(
    message: Optional[Message] = None, realm: Optional[Realm] = None, no_previews: bool = False
) -> bool:
    if not settings.INLINE_IMAGE_PREVIEW:
        return False

    if no_previews:
        return False

    if realm is None and message is not None:
        realm = message.get_realm()

    if realm is None:
        # realm can be None for odd use cases
        # like generating documentation or running
        # test code
        return True

    return realm.inline_image_preview


def list_of_tlds() -> List[str]:
    # Skip a few overly-common false-positives from file extensions
    common_false_positives = {"java", "md", "mov", "py", "zip"}
    return sorted(tld_set - common_false_positives, key=len, reverse=True)


def walk_tree(
    root: Element, processor: Callable[[Element], Optional[_T]], stop_after_first: bool = False
) -> List[_T]:
    results = []
    queue = deque([root])

    while queue:
        currElement = queue.popleft()
        for child in currElement:
            queue.append(child)

            result = processor(child)
            if result is not None:
                results.append(result)
                if stop_after_first:
                    return results

    return results


@dataclass
class ElementFamily:
    grandparent: Optional[Element]
    parent: Element
    child: Element
    in_blockquote: bool


T = TypeVar("T")


class ResultWithFamily(Generic[T]):
    family: ElementFamily
    result: T

    def __init__(self, family: ElementFamily, result: T) -> None:
        self.family = family
        self.result = result


class ElementPair:
    parent: Optional["ElementPair"]
    value: Element

    def __init__(self, parent: Optional["ElementPair"], value: Element) -> None:
        self.parent = parent
        self.value = value


def walk_tree_with_family(
    root: Element,
    processor: Callable[[Element], Optional[_T]],
) -> List[ResultWithFamily[_T]]:
    results = []

    queue = deque([ElementPair(parent=None, value=root)])
    while queue:
        currElementPair = queue.popleft()
        for child in currElementPair.value:
            queue.append(ElementPair(parent=currElementPair, value=child))
            result = processor(child)
            if result is not None:
                if currElementPair.parent is not None:
                    grandparent_element = currElementPair.parent
                    grandparent: Optional[Element] = grandparent_element.value
                else:
                    grandparent = None
                family = ElementFamily(
                    grandparent=grandparent,
                    parent=currElementPair.value,
                    child=child,
                    in_blockquote=has_blockquote_ancestor(currElementPair),
                )

                results.append(
                    ResultWithFamily(
                        family=family,
                        result=result,
                    )
                )

    return results


def has_blockquote_ancestor(element_pair: Optional[ElementPair]) -> bool:
    if element_pair is None:
        return False
    elif element_pair.value.tag == "blockquote":
        return True
    else:
        return has_blockquote_ancestor(element_pair.parent)


@cache_with_key(lambda tweet_id: tweet_id, cache_name="database")
def fetch_tweet_data(tweet_id: str) -> Optional[Dict[str, Any]]:
    # Twitter removed support for the v1 API that this integration
    # used. Given that, there's no point wasting time trying to make
    # network requests to Twitter. But we leave this function, because
    # existing cached renderings for Tweets is useful. We throw an
    # exception rather than returning `None` to avoid caching that the
    # link doesn't exist.
    raise NotImplementedError("Twitter desupported their v1 API")


class OpenGraphSession(OutgoingSession):
    def __init__(self) -> None:
        super().__init__(role="markdown", timeout=1)


def fetch_open_graph_image(url: str) -> Optional[Dict[str, Any]]:
    og: Dict[str, Optional[str]] = {"image": None, "title": None, "desc": None}

    try:
        with OpenGraphSession().get(
            url, headers={"Accept": "text/html,application/xhtml+xml"}, stream=True
        ) as res:
            if res.status_code != requests.codes.ok:
                return None

            mimetype, options = cgi.parse_header(res.headers["Content-Type"])
            if mimetype not in ("text/html", "application/xhtml+xml"):
                return None
            html = mimetype == "text/html"

            res.raw.decode_content = True
            for event, element in lxml.etree.iterparse(
                res.raw, events=("start",), no_network=True, remove_comments=True, html=html
            ):
                parent = element.getparent()
                if parent is not None:
                    # Reduce memory usage.
                    parent.text = None
                    parent.remove(element)

                if element.tag in ("body", "{http://www.w3.org/1999/xhtml}body"):
                    break
                elif element.tag in ("meta", "{http://www.w3.org/1999/xhtml}meta"):
                    if element.get("property") == "og:image":
                        content = element.get("content")
                        if content is not None:
                            og["image"] = urljoin(res.url, content)
                    elif element.get("property") == "og:title":
                        og["title"] = element.get("content")
                    elif element.get("property") == "og:description":
                        og["desc"] = element.get("content")

    except requests.RequestException:
        return None

    return None if og["image"] is None else og


def get_tweet_id(url: str) -> Optional[str]:
    parsed_url = urlsplit(url)
    if not (parsed_url.netloc == "twitter.com" or parsed_url.netloc.endswith(".twitter.com")):
        return None
    to_match = parsed_url.path
    # In old-style twitter.com/#!/wdaher/status/1231241234-style URLs,
    # we need to look at the fragment instead
    if parsed_url.path == "/" and len(parsed_url.fragment) > 5:
        to_match = parsed_url.fragment

    tweet_id_match = re.match(
        r"^!?/.*?/status(es)?/(?P<tweetid>\d{10,30})(/photo/[0-9])?/?$", to_match
    )
    if not tweet_id_match:
        return None
    return tweet_id_match.group("tweetid")


class InlineImageProcessor(markdown.treeprocessors.Treeprocessor):
    """
    Rewrite inline img tags to serve external content via Camo.

    This rewrites all images, except ones that are served from the current
    realm or global STATIC_URL. This is to ensure that each realm only loads
    images that are hosted on that realm or by the global installation,
    avoiding information leakage to external domains or between realms. We need
    to disable proxying of images hosted on the same realm, because otherwise
    we will break images in /user_uploads/, which require authorization to
    view.
    """

    def __init__(self, zmd: "ZulipMarkdown") -> None:
        super().__init__(zmd)
        self.zmd = zmd

    @override
    def run(self, root: Element) -> None:
        # Get all URLs from the blob
        found_imgs = walk_tree(root, lambda e: e if e.tag == "img" else None)
        for img in found_imgs:
            url = img.get("src")
            assert url is not None
            if is_static_or_current_realm_url(url, self.zmd.zulip_realm):
                # Don't rewrite images on our own site (e.g. emoji, user uploads).
                continue
            img.set("src", get_camo_url(url))


class InlineVideoProcessor(markdown.treeprocessors.Treeprocessor):
    """
    Rewrite inline video tags to serve external content via Camo.

    This rewrites all video, except ones that are served from the current
    realm or global STATIC_URL. This is to ensure that each realm only loads
    videos that are hosted on that realm or by the global installation,
    avoiding information leakage to external domains or between realms. We need
    to disable proxying of videos hosted on the same realm, because otherwise
    we will break videos in /user_uploads/, which require authorization to
    view.
    """

    def __init__(self, zmd: "ZulipMarkdown") -> None:
        super().__init__(zmd)
        self.zmd = zmd

    @override
    def run(self, root: Element) -> None:
        # Get all URLs from the blob
        found_videos = walk_tree(root, lambda e: e if e.tag == "video" else None)
        for video in found_videos:
            url = video.get("src")
            assert url is not None
            if is_static_or_current_realm_url(url, self.zmd.zulip_realm):
                # Don't rewrite videos on our own site (e.g. user uploads).
                continue
            # Pass down both camo generated URL and the original video URL to the client.
            # Camo URL is only used to generate preview of the video. When user plays the
            # video, we switch to the source url to fetch the video. This allows playing
            # the video with no load on our servers.
            video.set("src", get_camo_url(url))
            video.set("data-video-original-url", url)


class BacktickInlineProcessor(markdown.inlinepatterns.BacktickInlineProcessor):
    """Return a `<code>` element containing the matching text."""

    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        # Let upstream's implementation do its job as it is, we'll
        # just replace the text to not strip the group because it
        # makes it impossible to put leading/trailing whitespace in
        # an inline code span.
        el, start, end = ret = super().handleMatch(m, data)
        if el is not None and m.group(3):
            assert isinstance(el, Element)
            # upstream's code here is: m.group(3).strip() rather than m.group(3).
            el.text = markdown.util.AtomicString(markdown.util.code_escape(m.group(3)))
        return ret


# List from https://support.google.com/chromeos/bin/answer.py?hl=en&answer=183093
IMAGE_EXTENSIONS = [".bmp", ".gif", ".jpe", ".jpeg", ".jpg", ".png", ".webp"]


class InlineInterestingLinkProcessor(markdown.treeprocessors.Treeprocessor):
    TWITTER_MAX_IMAGE_HEIGHT = 400
    TWITTER_MAX_TO_PREVIEW = 3
    INLINE_PREVIEW_LIMIT_PER_MESSAGE = 24

    def __init__(self, zmd: "ZulipMarkdown") -> None:
        super().__init__(zmd)
        self.zmd = zmd

    def add_a(
        self,
        root: Element,
        image_url: str,
        link: str,
        title: Optional[str] = None,
        desc: Optional[str] = None,
        class_attr: str = "message_inline_image",
        data_id: Optional[str] = None,
        insertion_index: Optional[int] = None,
        already_thumbnailed: bool = False,
    ) -> None:
        desc = desc if desc is not None else ""

        # Update message.has_image attribute.
        if "message_inline_image" in class_attr and self.zmd.zulip_message:
            self.zmd.zulip_message.has_image = True

        if insertion_index is not None:
            div = Element("div")
            root.insert(insertion_index, div)
        else:
            div = SubElement(root, "div")

        div.set("class", class_attr)
        a = SubElement(div, "a")
        a.set("href", link)
        if title is not None:
            a.set("title", title)
        if data_id is not None:
            a.set("data-id", data_id)
        img = SubElement(a, "img")
        if (
            settings.THUMBNAIL_IMAGES
            and (not already_thumbnailed)
            and user_uploads_or_external(image_url)
        ):
            # We strip leading '/' from relative URLs here to ensure
            # consistency in what gets passed to /thumbnail
            image_url = image_url.lstrip("/")
            img.set("src", "/thumbnail?" + urlencode({"url": image_url, "size": "thumbnail"}))
            img.set(
                "data-src-fullsize", "/thumbnail?" + urlencode({"url": image_url, "size": "full"})
            )
        else:
            img.set("src", image_url)

        if class_attr == "message_inline_ref":
            summary_div = SubElement(div, "div")
            title_div = SubElement(summary_div, "div")
            title_div.set("class", "message_inline_image_title")
            title_div.text = title
            desc_div = SubElement(summary_div, "desc")
            desc_div.set("class", "message_inline_image_desc")

    def add_oembed_data(self, root: Element, link: str, extracted_data: UrlOEmbedData) -> None:
        if extracted_data.image is None:
            # Don't add an embed if an image is not found
            return

        if extracted_data.type == "photo":
            self.add_a(
                root,
                image_url=extracted_data.image,
                link=link,
                title=extracted_data.title,
            )

        elif extracted_data.type == "video":
            self.add_a(
                root,
                image_url=extracted_data.image,
                link=link,
                title=extracted_data.title,
                desc=extracted_data.description,
                class_attr="embed-video message_inline_image",
                data_id=extracted_data.html,
                already_thumbnailed=True,
            )

    def add_embed(self, root: Element, link: str, extracted_data: UrlEmbedData) -> None:
        if isinstance(extracted_data, UrlOEmbedData):
            self.add_oembed_data(root, link, extracted_data)
            return

        if extracted_data.image is None:
            # Don't add an embed if an image is not found
            return

        container = SubElement(root, "div")
        container.set("class", "message_embed")

        img_link = get_camo_url(extracted_data.image)
        img = SubElement(container, "a")
        img.set(
            "style",
            'background-image: url("'
            + img_link.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\a ")
            + '")',
        )
        img.set("href", link)
        img.set("class", "message_embed_image")

        data_container = SubElement(container, "div")
        data_container.set("class", "data-container")

        if extracted_data.title:
            title_elm = SubElement(data_container, "div")
            title_elm.set("class", "message_embed_title")
            a = SubElement(title_elm, "a")
            a.set("href", link)
            a.set("title", extracted_data.title)
            a.text = extracted_data.title
        if extracted_data.description:
            description_elm = SubElement(data_container, "div")
            description_elm.set("class", "message_embed_description")
            description_elm.text = extracted_data.description

    def get_actual_image_url(self, url: str) -> str:
        # Add specific per-site cases to convert image-preview URLs to image URLs.
        # See https://github.com/zulip/zulip/issues/4658 for more information
        parsed_url = urlsplit(url)
        if parsed_url.netloc == "github.com" or parsed_url.netloc.endswith(".github.com"):
            # https://github.com/zulip/zulip/blob/main/static/images/logo/zulip-icon-128x128.png ->
            # https://raw.githubusercontent.com/zulip/zulip/main/static/images/logo/zulip-icon-128x128.png
            split_path = parsed_url.path.split("/")
            if len(split_path) > 3 and split_path[3] == "blob":
                return urljoin(
                    "https://raw.githubusercontent.com", "/".join(split_path[0:3] + split_path[4:])
                )

        return url

    def is_image(self, url: str) -> bool:
        if not self.zmd.image_preview_enabled:
            return False
        parsed_url = urlsplit(url)
        # remove HTML URLs which end with image extensions that cannot be shorted
        if parsed_url.netloc == "pasteboard.co":
            return False

        return any(parsed_url.path.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)

    def corrected_image_source(self, url: str) -> Optional[str]:
        # This function adjusts any URLs from linx.li and
        # wikipedia.org to point to the actual image URL.  It's
        # structurally very similar to dropbox_image, and possibly
        # should be rewritten to use open graph, but has some value.
        parsed_url = urlsplit(url)
        if parsed_url.netloc.lower().endswith(".wikipedia.org") and parsed_url.path.startswith(
            "/wiki/File:"
        ):
            # Redirecting from "/wiki/File:" to "/wiki/Special:FilePath/File:"
            # A possible alternative, that avoids the redirect after hitting "Special:"
            # is using the first characters of md5($filename) to generate the URL
            newpath = parsed_url.path.replace("/wiki/File:", "/wiki/Special:FilePath/File:", 1)
            return parsed_url._replace(path=newpath).geturl()
        if parsed_url.netloc == "linx.li":
            return "https://linx.li/s" + parsed_url.path
        return None

    def dropbox_image(self, url: str) -> Optional[Dict[str, Any]]:
        # TODO: The returned Dict could possibly be a TypedDict in future.
        parsed_url = urlsplit(url)
        if parsed_url.netloc == "dropbox.com" or parsed_url.netloc.endswith(".dropbox.com"):
            is_album = parsed_url.path.startswith("/sc/") or parsed_url.path.startswith("/photos/")
            # Only allow preview Dropbox shared links
            if not (
                parsed_url.path.startswith("/s/") or parsed_url.path.startswith("/sh/") or is_album
            ):
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
                image_info = {}
            image_info["is_image"] = True
            image_info["image"] = parsed_url._replace(query="raw=1").geturl()

            return image_info
        return None

    def youtube_id(self, url: str) -> Optional[str]:
        if not self.zmd.image_preview_enabled:
            return None

        id = None
        split_url = urlsplit(url)
        if split_url.scheme in ("http", "https"):
            if split_url.hostname in (
                "m.youtube.com",
                "www.youtube.com",
                "www.youtube-nocookie.com",
                "youtube.com",
                "youtube-nocookie.com",
            ):
                query = parse_qs(split_url.query)
                if split_url.path in ("/watch", "/watch_popup") and "v" in query:
                    id = query["v"][0]
                elif split_url.path == "/watch_videos" and "video_ids" in query:
                    id = query["video_ids"][0].split(",", 1)[0]
                elif split_url.path.startswith(("/embed/", "/shorts/", "/v/")):
                    id = split_url.path.split("/", 3)[2]
            elif split_url.hostname == "youtu.be" and split_url.path.startswith("/"):
                id = split_url.path[len("/") :]

        if id is not None and re.fullmatch(r"[0-9A-Za-z_-]+", id):
            return id
        return None

    def youtube_title(self, extracted_data: UrlEmbedData) -> Optional[str]:
        if extracted_data.title is not None:
            return f"YouTube - {extracted_data.title}"
        return None

    def youtube_image(self, url: str) -> Optional[str]:
        yt_id = self.youtube_id(url)

        if yt_id is not None:
            return f"https://i.ytimg.com/vi/{yt_id}/default.jpg"
        return None

    def vimeo_id(self, url: str) -> Optional[str]:
        if not self.zmd.image_preview_enabled:
            return None
        # (http|https)?:\/\/(www\.)?vimeo.com\/(?:channels\/(?:\w+\/)?|groups\/([^\/]*)\/videos\/|)(\d+)(?:|\/\?)
        # If it matches, match.group('id') is the video id.

        vimeo_re = (
            r"^((http|https)?:\/\/(www\.)?vimeo.com\/"
            r"(?:channels\/(?:\w+\/)?|groups\/"
            r"([^\/]*)\/videos\/|)(\d+)(?:|\/\?))$"
        )
        match = re.match(vimeo_re, url)
        if match is None:
            return None
        return match.group(5)

    def vimeo_title(self, extracted_data: UrlEmbedData) -> Optional[str]:
        if extracted_data.title is not None:
            return f"Vimeo - {extracted_data.title}"
        return None

    def twitter_text(
        self,
        text: str,
        urls: List[Dict[str, str]],
        user_mentions: List[Dict[str, Any]],
        media: List[Dict[str, Any]],
    ) -> Element:
        """
        Use data from the Twitter API to turn links, mentions and media into A
        tags. Also convert Unicode emojis to images.

        This works by using the URLs, user_mentions and media data from
        the twitter API and searching for Unicode emojis in the text using
        `POSSIBLE_EMOJI_RE`.

        The first step is finding the locations of the URLs, mentions, media and
        emoji in the text. For each match we build a dictionary with type, the start
        location, end location, the URL to link to, and the text(codepoint and title
        in case of emojis) to be used in the link(image in case of emojis).

        Next we sort the matches by start location. And for each we add the
        text from the end of the last link to the start of the current link to
        the output. The text needs to added to the text attribute of the first
        node (the P tag) or the tail the last link created.

        Finally we add any remaining text to the last node.
        """

        to_process: List[Dict[str, Any]] = []
        # Build dicts for URLs
        for url_data in urls:
            to_process.extend(
                {
                    "type": "url",
                    "start": match.start(),
                    "end": match.end(),
                    "url": url_data["url"],
                    "text": url_data["expanded_url"],
                }
                for match in re.finditer(re.escape(url_data["url"]), text, re.IGNORECASE)
            )
        # Build dicts for mentions
        for user_mention in user_mentions:
            screen_name = user_mention["screen_name"]
            mention_string = "@" + screen_name
            to_process.extend(
                {
                    "type": "mention",
                    "start": match.start(),
                    "end": match.end(),
                    "url": "https://twitter.com/" + quote(screen_name),
                    "text": mention_string,
                }
                for match in re.finditer(re.escape(mention_string), text, re.IGNORECASE)
            )
        # Build dicts for media
        for media_item in media:
            short_url = media_item["url"]
            expanded_url = media_item["expanded_url"]
            to_process.extend(
                {
                    "type": "media",
                    "start": match.start(),
                    "end": match.end(),
                    "url": short_url,
                    "text": expanded_url,
                }
                for match in re.finditer(re.escape(short_url), text, re.IGNORECASE)
            )
        # Build dicts for emojis
        for match in POSSIBLE_EMOJI_RE.finditer(text):
            orig_syntax = match.group("syntax")
            codepoint = emoji_to_hex_codepoint(unqualify_emoji(orig_syntax))
            if codepoint in codepoint_to_name:
                display_string = ":" + codepoint_to_name[codepoint] + ":"
                to_process.append(
                    {
                        "type": "emoji",
                        "start": match.start(),
                        "end": match.end(),
                        "codepoint": codepoint,
                        "title": display_string,
                    }
                )

        to_process.sort(key=lambda x: x["start"])
        p = current_node = Element("p")

        def set_text(text: str) -> None:
            """
            Helper to set the text or the tail of the current_node
            """
            if current_node == p:
                current_node.text = text
            else:
                current_node.tail = text

        db_data: Optional[DbData] = self.zmd.zulip_db_data
        current_index = 0
        for item in to_process:
            # The text we want to link starts in already linked text skip it
            if item["start"] < current_index:
                continue
            # Add text from the end of last link to the start of the current
            # link
            set_text(text[current_index : item["start"]])
            current_index = item["end"]
            if item["type"] != "emoji":
                elem = url_to_a(db_data, item["url"], item["text"])
                assert isinstance(elem, Element)
            else:
                elem = make_emoji(item["codepoint"], item["title"])
            current_node = elem
            p.append(elem)

        # Add any unused text
        set_text(text[current_index:])
        return p

    def twitter_link(self, url: str) -> Optional[Element]:
        tweet_id = get_tweet_id(url)

        if tweet_id is None:
            return None

        try:
            res = fetch_tweet_data(tweet_id)
            if res is None:
                return None
            user: Dict[str, Any] = res["user"]
            tweet = Element("div")
            tweet.set("class", "twitter-tweet")
            img_a = SubElement(tweet, "a")
            img_a.set("href", url)
            profile_img = SubElement(img_a, "img")
            profile_img.set("class", "twitter-avatar")
            # For some reason, for, e.g. tweet 285072525413724161,
            # python-twitter does not give us a
            # profile_image_url_https, but instead puts that URL in
            # profile_image_url. So use _https if available, but fall
            # back gracefully.
            image_url = user.get("profile_image_url_https", user["profile_image_url"])
            profile_img.set("src", image_url)

            text = html.unescape(res["full_text"])
            urls = res.get("urls", [])
            user_mentions = res.get("user_mentions", [])
            media: List[Dict[str, Any]] = res.get("media", [])
            p = self.twitter_text(text, urls, user_mentions, media)
            tweet.append(p)

            span = SubElement(tweet, "span")
            span.text = "- {} (@{})".format(user["name"], user["screen_name"])

            # Add image previews
            for media_item in media:
                # Only photos have a preview image
                if media_item["type"] != "photo":
                    continue

                # Find the image size that is smaller than
                # TWITTER_MAX_IMAGE_HEIGHT px tall or the smallest
                size_name_tuples = sorted(
                    media_item["sizes"].items(), reverse=True, key=lambda x: x[1]["h"]
                )
                for size_name, size in size_name_tuples:
                    if size["h"] < self.TWITTER_MAX_IMAGE_HEIGHT:
                        break

                media_url = "{}:{}".format(media_item["media_url_https"], size_name)
                img_div = SubElement(tweet, "div")
                img_div.set("class", "twitter-image")
                img_a = SubElement(img_div, "a")
                img_a.set("href", media_item["url"])
                img = SubElement(img_a, "img")
                img.set("src", media_url)

            return tweet
        except NotImplementedError:
            return None
        except Exception:
            # We put this in its own try-except because it requires external
            # connectivity. If Twitter flakes out, we don't want to not-render
            # the entire message; we just want to not show the Twitter preview.
            markdown_logger.warning("Error building Twitter link", exc_info=True)
            return None

    def get_url_data(self, e: Element) -> Optional[Tuple[str, Optional[str]]]:
        if e.tag == "a":
            url = e.get("href")
            assert url is not None
            return (url, e.text)
        return None

    def get_inlining_information(
        self,
        root: Element,
        found_url: ResultWithFamily[Tuple[str, Optional[str]]],
    ) -> LinkInfo:
        grandparent = found_url.family.grandparent
        parent = found_url.family.parent
        ahref_element = found_url.family.child
        (url, text) = found_url.result

        # url != text usually implies a named link, which we opt not to remove
        url_eq_text = text is None or url == text
        title = None if url_eq_text else text
        info: LinkInfo = {
            "parent": root,
            "title": title,
            "index": None,
            "remove": None,
        }

        if parent.tag == "li":
            info["parent"] = parent
            if not parent.text and not ahref_element.tail and url_eq_text:
                info["remove"] = ahref_element

        elif parent.tag == "p":
            assert grandparent is not None
            parent_index = None
            for index, uncle in enumerate(grandparent):
                if uncle is parent:
                    parent_index = index
                    break

            # Append to end of list of grandparent's children as normal
            info["parent"] = grandparent

            if (
                len(parent) == 1
                and (not parent.text or parent.text == "\n")
                and not ahref_element.tail
                and url_eq_text
            ):
                info["remove"] = parent

            if parent_index is not None:
                info["index"] = self.find_proper_insertion_index(grandparent, parent, parent_index)

        return info

    def handle_image_inlining(
        self,
        root: Element,
        found_url: ResultWithFamily[Tuple[str, Optional[str]]],
    ) -> None:
        info = self.get_inlining_information(root, found_url)
        (url, text) = found_url.result
        actual_url = self.get_actual_image_url(url)
        self.add_a(
            info["parent"],
            image_url=actual_url,
            link=url,
            title=info["title"],
            insertion_index=info["index"],
        )
        if info["remove"] is not None:
            info["parent"].remove(info["remove"])

    def handle_tweet_inlining(
        self,
        root: Element,
        found_url: ResultWithFamily[Tuple[str, Optional[str]]],
        twitter_data: Element,
    ) -> None:
        info = self.get_inlining_information(root, found_url)

        if info["index"] is not None:
            div = Element("div")
            root.insert(info["index"], div)
        else:
            div = SubElement(root, "div")

        div.set("class", "inline-preview-twitter")
        div.insert(0, twitter_data)

    def handle_youtube_url_inlining(
        self,
        root: Element,
        found_url: ResultWithFamily[Tuple[str, Optional[str]]],
        yt_image: str,
    ) -> None:
        info = self.get_inlining_information(root, found_url)
        (url, text) = found_url.result
        yt_id = self.youtube_id(url)
        self.add_a(
            info["parent"],
            image_url=yt_image,
            link=url,
            class_attr="youtube-video message_inline_image",
            data_id=yt_id,
            insertion_index=info["index"],
            already_thumbnailed=True,
        )

    def find_proper_insertion_index(
        self, grandparent: Element, parent: Element, parent_index_in_grandparent: int
    ) -> int:
        # If there are several inline images from same paragraph, ensure that
        # they are in correct (and not opposite) order by inserting after last
        # inline image from paragraph 'parent'

        parent_links = [ele.attrib["href"] for ele in parent.iter(tag="a")]
        insertion_index = parent_index_in_grandparent

        while True:
            insertion_index += 1
            if insertion_index >= len(grandparent):
                return insertion_index

            uncle = grandparent[insertion_index]
            inline_image_classes = {
                "message_inline_image",
                "message_inline_ref",
                "inline-preview-twitter",
            }
            if (
                uncle.tag != "div"
                or "class" not in uncle.attrib
                or not (set(uncle.attrib["class"].split()) & inline_image_classes)
            ):
                return insertion_index

            uncle_link = uncle.find("a")
            assert uncle_link is not None
            if uncle_link.attrib["href"] not in parent_links:
                return insertion_index

    def is_video(self, url: str) -> bool:
        if not self.zmd.image_preview_enabled:
            return False

        url_type = mimetypes.guess_type(url)[0]
        # Support only video formats (containers) that are supported cross-browser and cross-device. As per
        # https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Containers#index_of_media_container_formats_file_types
        # MP4 and WebM are the only formats that are widely supported.
        supported_mimetypes = ["video/mp4", "video/webm"]
        return url_type in supported_mimetypes

    def add_video(
        self,
        root: Element,
        url: str,
        title: Optional[str],
        class_attr: str = "message_inline_image message_inline_video",
        insertion_index: Optional[int] = None,
    ) -> None:
        if insertion_index is not None:
            div = Element("div")
            root.insert(insertion_index, div)
        else:
            div = SubElement(root, "div")

        div.set("class", class_attr)
        # Add `a` tag so that the syntax of video matches with
        # other media types and clients don't get confused.
        a = SubElement(div, "a")
        a.set("href", url)
        if title:
            a.set("title", title)
        video = SubElement(a, "video")
        video.set("src", url)
        video.set("preload", "metadata")

    def handle_video_inlining(
        self, root: Element, found_url: ResultWithFamily[Tuple[str, Optional[str]]]
    ) -> None:
        info = self.get_inlining_information(root, found_url)
        url = found_url.result[0]

        self.add_video(info["parent"], url, info["title"], insertion_index=info["index"])

        if info["remove"] is not None:
            info["parent"].remove(info["remove"])

    @override
    def run(self, root: Element) -> None:
        # Get all URLs from the blob
        found_urls = walk_tree_with_family(root, self.get_url_data)
        unique_urls = {found_url.result[0] for found_url in found_urls}
        # Collect unique URLs which are not quoted as we don't do
        # inline previews for links inside blockquotes.
        unique_previewable_urls = {
            found_url.result[0] for found_url in found_urls if not found_url.family.in_blockquote
        }

        # Set has_link and similar flags whenever a message is processed by Markdown
        if self.zmd.zulip_message:
            self.zmd.zulip_message.has_link = len(found_urls) > 0
            self.zmd.zulip_message.has_image = False  # This is updated in self.add_a

            for url in unique_urls:
                # Due to rewrite_local_links_to_relative, we need to
                # handle both relative URLs beginning with
                # `/user_uploads` and beginning with `user_uploads`.
                # This urllib construction converts the latter into
                # the former.
                parsed_url = urlsplit(urljoin("/", url))
                host = parsed_url.netloc

                if host != "" and (
                    self.zmd.zulip_realm is None or host != self.zmd.zulip_realm.host
                ):
                    continue

                if not parsed_url.path.startswith("/user_uploads/"):
                    continue

                path_id = parsed_url.path[len("/user_uploads/") :]
                self.zmd.zulip_rendering_result.potential_attachment_path_ids.append(path_id)

        if len(found_urls) == 0:
            return

        if len(unique_previewable_urls) > self.INLINE_PREVIEW_LIMIT_PER_MESSAGE:
            return

        processed_urls: Set[str] = set()
        rendered_tweet_count = 0

        for found_url in found_urls:
            (url, text) = found_url.result

            if url in unique_previewable_urls and url not in processed_urls:
                processed_urls.add(url)
            else:
                continue

            if self.is_video(url):
                self.handle_video_inlining(root, found_url)
                continue

            dropbox_image = self.dropbox_image(url)
            if dropbox_image is not None:
                class_attr = "message_inline_ref"
                is_image = dropbox_image["is_image"]
                if is_image:
                    class_attr = "message_inline_image"
                    # Not making use of title and description of images
                self.add_a(
                    root,
                    image_url=dropbox_image["image"],
                    link=url,
                    title=dropbox_image.get("title"),
                    desc=dropbox_image.get("desc", ""),
                    class_attr=class_attr,
                    already_thumbnailed=True,
                )
                continue

            if self.is_image(url):
                image_source = self.corrected_image_source(url)
                if image_source is not None:
                    found_url = ResultWithFamily(
                        family=found_url.family,
                        result=(image_source, image_source),
                    )
                self.handle_image_inlining(root, found_url)
                continue

            netloc = urlsplit(url).netloc
            if netloc == "" or (
                self.zmd.zulip_realm is not None and netloc == self.zmd.zulip_realm.host
            ):
                # We don't have a strong use case for doing URL preview for relative links.
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
                self.handle_tweet_inlining(root, found_url, twitter_data)
                continue
            youtube = self.youtube_image(url)
            if youtube is not None:
                self.handle_youtube_url_inlining(root, found_url, youtube)
                # NOTE: We don't `continue` here, to allow replacing the URL with
                # the title, if INLINE_URL_EMBED_PREVIEW feature is enabled.
                # The entire preview would ideally be shown only if the feature
                # is enabled, but URL previews are a beta feature and YouTube
                # previews are pretty stable.

            db_data: Optional[DbData] = self.zmd.zulip_db_data
            if db_data and db_data.sent_by_bot:
                continue

            if not self.zmd.url_embed_preview_enabled:
                continue

            if self.zmd.url_embed_data is None or url not in self.zmd.url_embed_data:
                self.zmd.zulip_rendering_result.links_for_preview.add(url)
                continue

            # Existing but being None means that we did process the
            # URL, but it was not valid to preview.
            extracted_data = self.zmd.url_embed_data[url]
            if extracted_data is None:
                continue

            if youtube is not None:
                title = self.youtube_title(extracted_data)
                if title is not None:
                    if url == text:
                        found_url.family.child.text = title
                    else:
                        found_url.family.child.text = text
                continue
            self.add_embed(root, url, extracted_data)
            if self.vimeo_id(url):
                title = self.vimeo_title(extracted_data)
                if title:
                    if url == text:
                        found_url.family.child.text = title
                    else:
                        found_url.family.child.text = text


class CompiledInlineProcessor(markdown.inlinepatterns.InlineProcessor):
    def __init__(self, compiled_re: Pattern[str], zmd: "ZulipMarkdown") -> None:
        # This is similar to the superclass's small __init__ function,
        # but we skip the compilation step and let the caller give us
        # a compiled regex.
        self.compiled_re = compiled_re
        self.md = zmd
        self.zmd = zmd


class Timestamp(markdown.inlinepatterns.Pattern):
    @override
    def handleMatch(self, match: Match[str]) -> Optional[Element]:
        time_input_string = match.group("time")
        try:
            timestamp = dateutil.parser.parse(time_input_string, tzinfos=common_timezones)
        except (ValueError, OverflowError):
            try:
                timestamp = datetime.fromtimestamp(float(time_input_string), tz=timezone.utc)
            except ValueError:
                timestamp = None

        if not timestamp:
            error_element = Element("span")
            error_element.set("class", "timestamp-error")
            error_element.text = markdown.util.AtomicString(
                f"Invalid time format: {time_input_string}"
            )
            return error_element

        # Use HTML5 <time> element for valid timestamps.
        time_element = Element("time")
        if timestamp.tzinfo:
            timestamp = timestamp.astimezone(timezone.utc)
        else:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        time_element.set("datetime", timestamp.isoformat().replace("+00:00", "Z"))
        # Set text to initial input, so simple clients translating
        # HTML to text will at least display something.
        time_element.text = markdown.util.AtomicString(time_input_string)
        return time_element


# From https://unicode.org/reports/tr51/#EBNF_and_Regex. Keep this synced with `possible_emoji_regex`.
POSSIBLE_EMOJI_RE = regex.compile(
    r"""(?P<syntax>
\p{RI} \p{RI}
| \p{Emoji}
  (?: \p{Emoji_Modifier}
  | \uFE0F \u20E3?
  | [\U000E0020-\U000E007E]+ \U000E007F
  )?
  (?: \u200D
    (?: \p{RI} \p{RI}
    | \p{Emoji}
      (?: \p{Emoji_Modifier}
      | \uFE0F \u20E3?
      | [\U000E0020-\U000E007E]+ \U000E007F
      )?
    )
  )*)
""",
    regex.VERBOSE,
)


def make_emoji(codepoint: str, display_string: str) -> Element:
    # Replace underscore in emoji's title with space
    title = display_string[1:-1].replace("_", " ")
    span = Element("span")
    span.set("class", f"emoji emoji-{codepoint}")
    span.set("title", title)
    span.set("role", "img")
    span.set("aria-label", title)
    span.text = markdown.util.AtomicString(display_string)
    return span


def make_realm_emoji(src: str, display_string: str) -> Element:
    elt = Element("img")
    elt.set("src", src)
    elt.set("class", "emoji")
    elt.set("alt", display_string)
    elt.set("title", display_string[1:-1].replace("_", " "))
    return elt


class EmoticonTranslation(markdown.inlinepatterns.Pattern):
    """Translates emoticons like `:)` into emoji like `:smile:`."""

    def __init__(self, pattern: str, zmd: "ZulipMarkdown") -> None:
        super().__init__(pattern, zmd)
        self.zmd = zmd

    @override
    def handleMatch(self, match: Match[str]) -> Optional[Element]:
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        if db_data is None or not db_data.translate_emoticons:
            return None

        emoticon = match.group("emoticon")
        translated = translate_emoticons(emoticon)
        name = translated[1:-1]
        return make_emoji(name_to_codepoint[name], translated)


TEXT_PRESENTATION_RE = regex.compile(r"\P{Emoji_Presentation}\u20E3?")


class UnicodeEmoji(CompiledInlineProcessor):
    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, match: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        orig_syntax = match.group("syntax")

        # We want to avoid turning things like arrows (↔) and keycaps (numbers
        # in boxes) into qualified emoji.
        # More specifically, we skip anything with text in the second column of
        # this table https://unicode.org/Public/emoji/1.0/emoji-data.txt
        if TEXT_PRESENTATION_RE.fullmatch(orig_syntax):
            return None, None, None

        codepoint = emoji_to_hex_codepoint(unqualify_emoji(orig_syntax))
        if codepoint in codepoint_to_name:
            display_string = ":" + codepoint_to_name[codepoint] + ":"
            return make_emoji(codepoint, display_string), match.start(), match.end()
        else:
            return None, None, None


class Emoji(markdown.inlinepatterns.Pattern):
    def __init__(self, pattern: str, zmd: "ZulipMarkdown") -> None:
        super().__init__(pattern, zmd)
        self.zmd = zmd

    @override
    def handleMatch(self, match: Match[str]) -> Optional[Union[str, Element]]:
        orig_syntax = match.group("syntax")
        name = orig_syntax[1:-1]

        active_realm_emoji: Dict[str, EmojiInfo] = {}
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        if db_data is not None:
            active_realm_emoji = db_data.active_realm_emoji

        if name in active_realm_emoji:
            return make_realm_emoji(active_realm_emoji[name]["source_url"], orig_syntax)
        elif name == "zulip":
            # We explicitly do not use staticfiles to generate the URL
            # for this, so that it is portable if exported.
            return make_realm_emoji(
                "/static/generated/emoji/images/emoji/unicode/zulip.png", orig_syntax
            )
        elif name in name_to_codepoint:
            return make_emoji(name_to_codepoint[name], orig_syntax)
        else:
            return orig_syntax


def content_has_emoji_syntax(content: str) -> bool:
    return re.search(EMOJI_REGEX, content) is not None


class Tex(markdown.inlinepatterns.Pattern):
    @override
    def handleMatch(self, match: Match[str]) -> Union[str, Element]:
        rendered = render_tex(match.group("body"), is_inline=True)
        if rendered is not None:
            return self.md.htmlStash.store(rendered)
        else:  # Something went wrong while rendering
            span = Element("span")
            span.set("class", "tex-error")
            span.text = markdown.util.AtomicString("$$" + match.group("body") + "$$")
            return span


def sanitize_url(url: str) -> Optional[str]:
    """
    Sanitize a URL against XSS attacks.
    See the docstring on markdown.inlinepatterns.LinkPattern.sanitize_url.
    """
    try:
        parts = urlsplit(url.replace(" ", "%20"))
        scheme, netloc, path, query, fragment = parts
    except ValueError:
        # Bad URL - so bad it couldn't be parsed.
        return ""

    # If there is no scheme or netloc and there is a '@' in the path,
    # treat it as a mailto: and set the appropriate scheme
    if scheme == "" and netloc == "" and "@" in path:
        scheme = "mailto"
    elif scheme == "" and netloc == "" and len(path) > 0 and path[0] == "/":
        # Allow domain-relative links
        return urlunsplit(("", "", path, query, fragment))
    elif (scheme, netloc, path, query) == ("", "", "", "") and len(fragment) > 0:
        # Allow fragment links
        return urlunsplit(("", "", "", "", fragment))

    # Zulip modification: If scheme is not specified, assume http://
    # We re-enter sanitize_url because netloc etc. need to be re-parsed.
    if not scheme:
        return sanitize_url("http://" + url)

    # Upstream code will accept a URL like javascript://foo because it
    # appears to have a netloc.  Additionally there are plenty of other
    # schemes that do weird things like launch external programs.  To be
    # on the safe side, we allow a fixed set of schemes.
    if scheme not in allowed_schemes:
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

    # URL passes all tests. Return URL as-is.
    return urlunsplit((scheme, netloc, path, query, fragment))


def url_to_a(
    db_data: Optional[DbData], url: str, text: Optional[str] = None
) -> Union[Element, str]:
    a = Element("a")

    href = sanitize_url(url)
    if href is None:
        # Rejected by sanitize_url; render it as plain text.
        return url
    if text is None:
        text = markdown.util.AtomicString(url)

    href = rewrite_local_links_to_relative(db_data, href)

    a.set("href", href)
    a.text = text
    return a


class CompiledPattern(markdown.inlinepatterns.Pattern):
    def __init__(self, compiled_re: Pattern[str], zmd: "ZulipMarkdown") -> None:
        # This is similar to the superclass's small __init__ function,
        # but we skip the compilation step and let the caller give us
        # a compiled regex.
        self.compiled_re = compiled_re
        self.md = zmd
        self.zmd = zmd


class AutoLink(CompiledPattern):
    @override
    def handleMatch(self, match: Match[str]) -> ElementStringNone:
        url = match.group("url")
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        return url_to_a(db_data, url)


class OListProcessor(sane_lists.SaneOListProcessor):
    def __init__(self, parser: BlockParser) -> None:
        parser.md.tab_length = 2
        super().__init__(parser)
        parser.md.tab_length = 4


class UListProcessor(sane_lists.SaneUListProcessor):
    """Unordered lists, but with 2-space indent"""

    def __init__(self, parser: BlockParser) -> None:
        parser.md.tab_length = 2
        super().__init__(parser)
        parser.md.tab_length = 4


class ListIndentProcessor(markdown.blockprocessors.ListIndentProcessor):
    """Process unordered list blocks.

    Based on markdown.blockprocessors.ListIndentProcessor, but with 2-space indent
    """

    def __init__(self, parser: BlockParser) -> None:
        # HACK: Set the tab length to 2 just for the initialization of
        # this class, so that bulleted lists (and only bulleted lists)
        # work off 2-space indentation.
        parser.md.tab_length = 2
        super().__init__(parser)
        parser.md.tab_length = 4


class HashHeaderProcessor(markdown.blockprocessors.HashHeaderProcessor):
    """Process hash headers.

    Based on markdown.blockprocessors.HashHeaderProcessor, but requires space for heading.
    """

    # Original regex for hashheader is
    # RE = re.compile(r'(?:^|\n)(?P<level>#{1,6})(?P<header>(?:\\.|[^\\])*?)#*(?:\n|$)')
    RE = re.compile(r"(?:^|\n)(?P<level>#{1,6})\s(?P<header>(?:\\.|[^\\])*?)#*(?:\n|$)")


class BlockQuoteProcessor(markdown.blockprocessors.BlockQuoteProcessor):
    """Process block quotes.

    Based on markdown.blockprocessors.BlockQuoteProcessor, but with 2-space indent
    """

    # Original regex for blockquote is RE = re.compile(r'(^|\n)[ ]{0,3}>[ ]?(.*)')
    RE = re.compile(r"(^|\n)(?!(?:[ ]{0,3}>\s*(?:$|\n))*(?:$|\n))[ ]{0,3}>[ ]?(.*)")

    # run() is very slightly forked from the base class; see notes below.
    @override
    def run(self, parent: Element, blocks: List[str]) -> None:
        block = blocks.pop(0)
        m = self.RE.search(block)
        if m:
            before = block[: m.start()]  # Lines before blockquote
            # Pass lines before blockquote in recursively for parsing first.
            self.parser.parseBlocks(parent, [before])
            # Remove ``> `` from beginning of each line.
            block = "\n".join([self.clean(line) for line in block[m.start() :].split("\n")])

        # Zulip modification: The next line is patched to match
        # CommonMark rather than original Markdown.  In original
        # Markdown, blockquotes with a blank line between them were
        # merged, which makes it impossible to break a blockquote with
        # a blank line intentionally.
        #
        # This is a new blockquote. Create a new parent element.
        quote = SubElement(parent, "blockquote")

        # Recursively parse block with blockquote as parent.
        # change parser state so blockquotes embedded in lists use p tags
        self.parser.state.set("blockquote")
        self.parser.parseChunk(quote, block)
        self.parser.state.reset()

    @override
    def clean(self, line: str) -> str:
        # Silence all the mentions inside blockquotes
        line = mention.MENTIONS_RE.sub(lambda m: "@_**{}**".format(m.group("match")), line)
        # Silence all the user group mentions inside blockquotes
        line = mention.USER_GROUP_MENTIONS_RE.sub(lambda m: "@_*{}*".format(m.group("match")), line)

        # And then run the upstream processor's code for removing the '>'
        return super().clean(line)


@dataclass
class Fence:
    fence_str: str
    is_code: bool


class MarkdownListPreprocessor(markdown.preprocessors.Preprocessor):
    """Allows list blocks that come directly after another block
    to be rendered as a list.

    Detects paragraphs that have a matching list item that comes
    directly after a line of text, and inserts a newline between
    to satisfy Markdown"""

    LI_RE = re.compile(r"^[ ]*([*+-]|\d\.)[ ]+(.*)", re.MULTILINE)

    @override
    def run(self, lines: List[str]) -> List[str]:
        """Insert a newline between a paragraph and ulist if missing"""
        inserts = 0
        in_code_fence: bool = False
        open_fences: List[Fence] = []
        copy = lines[:]
        for i in range(len(lines) - 1):
            # Ignore anything that is inside a fenced code block but not quoted.
            # We ignore all lines where some parent is a non-quote code block.
            m = FENCE_RE.match(lines[i])
            if m:
                fence_str = m.group("fence")
                lang: Optional[str] = m.group("lang")
                is_code = lang not in ("quote", "quoted")
                matches_last_fence = (
                    fence_str == open_fences[-1].fence_str if open_fences else False
                )
                closes_last_fence = not lang and matches_last_fence

                if closes_last_fence:
                    open_fences.pop()
                else:
                    open_fences.append(Fence(fence_str, is_code))

                in_code_fence = any(fence.is_code for fence in open_fences)

            # If we're not in a fenced block and we detect an upcoming list
            # hanging off any block (including a list of another type), add
            # a newline.
            li1 = self.LI_RE.match(lines[i])
            li2 = self.LI_RE.match(lines[i + 1])
            if (
                not in_code_fence
                and lines[i]
                and (
                    (li2 and not li1)
                    or (li1 and li2 and (len(li1.group(1)) == 1) != (len(li2.group(1)) == 1))
                )
            ):
                copy.insert(i + inserts + 1, "")
                inserts += 1
        return copy


# Name for the outer capture group we use to separate whitespace and
# other delimiters from the actual content.  This value won't be an
# option in user-entered capture groups.
BEFORE_CAPTURE_GROUP = "linkifier_before_match"
OUTER_CAPTURE_GROUP = "linkifier_actual_match"
AFTER_CAPTURE_GROUP = "linkifier_after_match"


def prepare_linkifier_pattern(source: str) -> str:
    """Augment a linkifier so it only matches after start-of-string,
    whitespace, or opening delimiters, won't match if there are word
    characters directly after, and saves what was matched as
    OUTER_CAPTURE_GROUP."""

    # This NEL character (0x85) is interpolated via a variable,
    # because r"" strings cannot use backslash escapes.
    next_line = "\u0085"

    # We use an extended definition of 'whitespace' which is
    # equivalent to \p{White_Space} -- since \s in re2 only matches
    # ASCII spaces, and re2 does not support \p{White_Space}.
    return rf"""(?P<{BEFORE_CAPTURE_GROUP}>^|\s|{next_line}|\pZ|['"\(,:<])(?P<{OUTER_CAPTURE_GROUP}>{source})(?P<{AFTER_CAPTURE_GROUP}>$|[^\pL\pN])"""


# Given a regular expression pattern, linkifies groups that match it
# using the provided format string to construct the URL.
class LinkifierPattern(CompiledInlineProcessor):
    """Applied a given linkifier to the input"""

    def __init__(
        self,
        source_pattern: str,
        url_template: str,
        zmd: "ZulipMarkdown",
    ) -> None:
        # Do not write errors to stderr (this still raises exceptions)
        options = re2.Options()
        options.log_errors = False

        compiled_re2 = re2.compile(prepare_linkifier_pattern(source_pattern), options=options)

        self.prepared_url_template = uri_template.URITemplate(url_template)

        super().__init__(compiled_re2, zmd)

    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        url = url_to_a(
            db_data,
            self.prepared_url_template.expand(**m.groupdict()),
            markdown.util.AtomicString(m.group(OUTER_CAPTURE_GROUP)),
        )
        if isinstance(url, str):
            return None, None, None

        return (
            url,
            m.start(2),
            m.end(2),
        )


class UserMentionPattern(CompiledInlineProcessor):
    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        name = m.group("match")
        silent = m.group("silent") == "_"
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        if db_data is not None:
            topic_wildcard = mention.user_mention_matches_topic_wildcard(name)
            stream_wildcard = mention.user_mention_matches_stream_wildcard(name)

            # For @**|id** and @**name|id** mention syntaxes.
            id_syntax_match = re.match(r"(?P<full_name>.+)?\|(?P<user_id>\d+)$", name)
            if id_syntax_match:
                full_name = id_syntax_match.group("full_name")
                id = int(id_syntax_match.group("user_id"))
                user = db_data.mention_data.get_user_by_id(id)

                # For @**name|id**, we need to specifically check that
                # name matches the full_name of user in mention_data.
                # This enforces our decision that
                # @**user_1_name|id_for_user_2** should be invalid syntax.
                if full_name and user and user.full_name != full_name:
                    return None, None, None
            else:
                # For @**name** syntax.
                user = db_data.mention_data.get_user_by_name(name)

            user_id = None
            if stream_wildcard:
                if not silent:
                    self.zmd.zulip_rendering_result.mentions_stream_wildcard = True
                user_id = "*"
            elif topic_wildcard:
                if not silent:
                    self.zmd.zulip_rendering_result.mentions_topic_wildcard = True
            elif user is not None:
                assert isinstance(user, FullNameInfo)
                if not user.is_active:
                    silent = True

                if not silent:
                    self.zmd.zulip_rendering_result.mentions_user_ids.add(user.id)
                name = user.full_name
                user_id = str(user.id)
            else:
                # Don't highlight @mentions that don't refer to a valid user
                return None, None, None

            el = Element("span")
            if user_id:
                el.set("data-user-id", user_id)
            text = f"@{name}"
            if topic_wildcard:
                el.set("class", "topic-mention")
            else:
                el.set("class", "user-mention")
            if silent:
                el.set("class", el.get("class", "") + " silent")
                text = f"{name}"
            el.text = markdown.util.AtomicString(text)
            return el, m.start(), m.end()
        return None, None, None


class UserGroupMentionPattern(CompiledInlineProcessor):
    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        name = m.group("match")
        silent = m.group("silent") == "_"
        db_data: Optional[DbData] = self.zmd.zulip_db_data

        if db_data is not None:
            user_group = db_data.mention_data.get_user_group(name)
            if user_group:
                if not silent:
                    self.zmd.zulip_rendering_result.mentions_user_group_ids.add(user_group.id)
                name = user_group.name
                user_group_id = str(user_group.id)
            else:
                # Don't highlight @-mentions that don't refer to a valid user
                # group.
                return None, None, None

            el = Element("span")
            el.set("data-user-group-id", user_group_id)
            if silent:
                el.set("class", "user-group-mention silent")
                text = f"{name}"
            else:
                el.set("class", "user-group-mention")
                text = f"@{name}"
            el.text = markdown.util.AtomicString(text)
            return el, m.start(), m.end()
        return None, None, None


class StreamPattern(CompiledInlineProcessor):
    def find_stream_id(self, name: str) -> Optional[int]:
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        if db_data is None:
            return None
        stream_id = db_data.stream_names.get(name)
        return stream_id

    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        name = m.group("stream_name")

        stream_id = self.find_stream_id(name)
        if stream_id is None:
            return None, None, None
        el = Element("a")
        el.set("class", "stream")
        el.set("data-stream-id", str(stream_id))
        # TODO: We should quite possibly not be specifying the
        # href here and instead having the browser auto-add the
        # href when it processes a message with one of these, to
        # provide more clarity to API clients.
        # Also do the same for StreamTopicPattern.
        stream_url = encode_stream(stream_id, name)
        el.set("href", f"/#narrow/stream/{stream_url}")
        text = f"#{name}"
        el.text = markdown.util.AtomicString(text)
        return el, m.start(), m.end()


class StreamTopicPattern(CompiledInlineProcessor):
    def find_stream_id(self, name: str) -> Optional[int]:
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        if db_data is None:
            return None
        stream_id = db_data.stream_names.get(name)
        return stream_id

    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        stream_name = m.group("stream_name")
        topic_name = m.group("topic_name")

        stream_id = self.find_stream_id(stream_name)
        if stream_id is None or topic_name is None:
            return None, None, None
        el = Element("a")
        el.set("class", "stream-topic")
        el.set("data-stream-id", str(stream_id))
        stream_url = encode_stream(stream_id, stream_name)
        topic_url = hash_util_encode(topic_name)
        link = f"/#narrow/stream/{stream_url}/topic/{topic_url}"
        el.set("href", link)
        text = f"#{stream_name} > {topic_name}"
        el.text = markdown.util.AtomicString(text)
        return el, m.start(), m.end()


def possible_linked_stream_names(content: str) -> Set[str]:
    return {
        *re.findall(STREAM_LINK_REGEX, content, re.VERBOSE),
        *(
            match.group("stream_name")
            for match in re.finditer(STREAM_TOPIC_LINK_REGEX, content, re.VERBOSE)
        ),
    }


class AlertWordNotificationProcessor(markdown.preprocessors.Preprocessor):
    allowed_before_punctuation = {" ", "\n", "(", '"', ".", ",", "'", ";", "[", "*", "`", ">"}
    allowed_after_punctuation = {
        " ",
        "\n",
        ")",
        '",',
        "?",
        ":",
        ".",
        ",",
        "'",
        ";",
        "]",
        "!",
        "*",
        "`",
    }

    def __init__(self, zmd: "ZulipMarkdown") -> None:
        super().__init__(zmd)
        self.zmd = zmd

    def check_valid_start_position(self, content: str, index: int) -> bool:
        if index <= 0 or content[index] in self.allowed_before_punctuation:
            return True
        return False

    def check_valid_end_position(self, content: str, index: int) -> bool:
        if index >= len(content) or content[index] in self.allowed_after_punctuation:
            return True
        return False

    @override
    def run(self, lines: List[str]) -> List[str]:
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        if db_data is not None:
            # We check for alert words here, the set of which are
            # dependent on which users may see this message.
            #
            # Our caller passes in the list of possible_words.  We
            # don't do any special rendering; we just append the alert words
            # we find to the set self.zmd.zulip_rendering_result.user_ids_with_alert_words.

            realm_alert_words_automaton = db_data.realm_alert_words_automaton

            if realm_alert_words_automaton is not None:
                content = "\n".join(lines).lower()
                for end_index, (original_value, user_ids) in realm_alert_words_automaton.iter(
                    content
                ):
                    if self.check_valid_start_position(
                        content, end_index - len(original_value)
                    ) and self.check_valid_end_position(content, end_index + 1):
                        self.zmd.zulip_rendering_result.user_ids_with_alert_words.update(user_ids)
        return lines


class LinkInlineProcessor(markdown.inlinepatterns.LinkInlineProcessor):
    def __init__(self, pattern: str, zmd: "ZulipMarkdown") -> None:
        super().__init__(pattern, zmd)
        self.zmd = zmd

    def zulip_specific_link_changes(self, el: Element) -> Union[None, Element]:
        href = el.get("href")
        assert href is not None

        # Sanitize URL or don't parse link. See linkify_tests in markdown_test_cases for banned syntax.
        href = sanitize_url(self.unescape(href.strip()))
        if href is None:
            return None  # no-op; the link is not processed.

        # Rewrite local links to be relative
        db_data: Optional[DbData] = self.zmd.zulip_db_data
        href = rewrite_local_links_to_relative(db_data, href)

        # Make changes to <a> tag attributes
        el.set("href", href)

        # Show link href if title is empty
        if not el.text or not el.text.strip():
            el.text = href

        # Prevent linkifiers from running on the content of a Markdown link, breaking up the link.
        # This is a monkey-patch, but it might be worth sending a version of this change upstream.
        el.text = markdown.util.AtomicString(el.text)

        return el

    @override
    def handleMatch(  # type: ignore[override] # https://github.com/python/mypy/issues/10197
        self, m: Match[str], data: str
    ) -> Tuple[Union[Element, str, None], Optional[int], Optional[int]]:
        ret = super().handleMatch(m, data)
        if ret[0] is not None:
            el, match_start, index = ret
            assert isinstance(el, Element)
            el = self.zulip_specific_link_changes(el)
            if el is not None:
                return el, match_start, index
        return None, None, None


def get_sub_registry(r: markdown.util.Registry[T], keys: List[str]) -> markdown.util.Registry[T]:
    # Registry is a new class added by Python-Markdown to replace OrderedDict.
    # Since Registry doesn't support .keys(), it is easier to make a new
    # object instead of removing keys from the existing object.
    new_r = markdown.util.Registry[T]()
    for k in keys:
        new_r.register(r[k], k, r.get_index_for_name(k))
    return new_r


# These are used as keys ("linkifiers_keys") to md_engines and the respective
# linkifier caches
DEFAULT_MARKDOWN_KEY = -1
ZEPHYR_MIRROR_MARKDOWN_KEY = -2


class ZulipMarkdown(markdown.Markdown):
    zulip_message: Optional[Message]
    zulip_realm: Optional[Realm]
    zulip_db_data: Optional[DbData]
    zulip_rendering_result: MessageRenderingResult
    image_preview_enabled: bool
    url_embed_preview_enabled: bool
    url_embed_data: Optional[Dict[str, Optional[UrlEmbedData]]]

    def __init__(
        self,
        linkifiers: List[LinkifierDict],
        linkifiers_key: int,
        email_gateway: bool,
    ) -> None:
        self.linkifiers = linkifiers
        self.linkifiers_key = linkifiers_key
        self.email_gateway = email_gateway

        super().__init__(
            extensions=[
                nl2br.makeExtension(),
                tables.makeExtension(),
                codehilite.makeExtension(
                    linenums=False,
                    guess_lang=False,
                ),
            ],
        )
        self.set_output_format("html")

    @override
    def build_parser(self) -> Self:
        # Build the parser using selected default features from Python-Markdown.
        # The complete list of all available processors can be found in the
        # super().build_parser() function.
        #
        # Note: for any Python-Markdown updates, manually check if we want any
        # of the new features added upstream or not; they wouldn't get
        # included by default.
        self.preprocessors = self.build_preprocessors()
        self.parser = self.build_block_parser()
        self.inlinePatterns = self.build_inlinepatterns()
        self.treeprocessors = self.build_treeprocessors()
        self.postprocessors = self.build_postprocessors()
        self.handle_zephyr_mirror()
        return self

    def build_preprocessors(self) -> markdown.util.Registry[markdown.preprocessors.Preprocessor]:
        # We disable the following preprocessors from upstream:
        #
        # html_block - insecure
        # reference - references don't make sense in a chat context.
        preprocessors = markdown.util.Registry[markdown.preprocessors.Preprocessor]()
        preprocessors.register(MarkdownListPreprocessor(self), "hanging_lists", 35)
        preprocessors.register(
            markdown.preprocessors.NormalizeWhitespace(self), "normalize_whitespace", 30
        )
        preprocessors.register(fenced_code.FencedBlockPreprocessor(self), "fenced_code_block", 25)
        preprocessors.register(
            AlertWordNotificationProcessor(self), "custom_text_notifications", 20
        )
        return preprocessors

    def build_block_parser(self) -> BlockParser:
        # We disable the following blockparsers from upstream:
        #
        # indent - replaced by ours
        # setextheader - disabled; we only support hashheaders for headings
        # olist - replaced by ours
        # ulist - replaced by ours
        # quote - replaced by ours
        parser = BlockParser(self)
        parser.blockprocessors.register(
            markdown.blockprocessors.EmptyBlockProcessor(parser), "empty", 95
        )
        parser.blockprocessors.register(ListIndentProcessor(parser), "indent", 90)
        if not self.email_gateway:
            parser.blockprocessors.register(
                markdown.blockprocessors.CodeBlockProcessor(parser), "code", 85
            )
        parser.blockprocessors.register(HashHeaderProcessor(parser), "hashheader", 80)
        # We get priority 75 from 'table' extension
        parser.blockprocessors.register(markdown.blockprocessors.HRProcessor(parser), "hr", 70)
        parser.blockprocessors.register(OListProcessor(parser), "olist", 65)
        parser.blockprocessors.register(UListProcessor(parser), "ulist", 60)
        parser.blockprocessors.register(BlockQuoteProcessor(parser), "quote", 55)
        # We get priority 51 from our 'include' extension
        parser.blockprocessors.register(
            markdown.blockprocessors.ParagraphProcessor(parser), "paragraph", 50
        )
        return parser

    def build_inlinepatterns(self) -> markdown.util.Registry[markdown.inlinepatterns.Pattern]:
        # We disable the following upstream inline patterns:
        #
        # backtick -        replaced by ours
        # escape -          probably will re-add at some point.
        # link -            replaced by ours
        # image_link -      replaced by ours
        # autolink -        replaced by ours
        # automail -        replaced by ours
        # linebreak -       we use nl2br and consider that good enough
        # html -            insecure
        # reference -       references not useful
        # image_reference - references not useful
        # short_reference - references not useful
        # ---------------------------------------------------
        # strong_em -       for these three patterns,
        # strong2 -         we have our own versions where
        # emphasis2 -       we disable _ for bold and emphasis

        # Declare regexes for clean single line calls to .register().
        #
        # Custom strikethrough syntax: ~~foo~~
        DEL_RE = r"(?<!~)(\~\~)([^~\n]+?)(\~\~)(?!~)"
        # Custom bold syntax: **foo** but not __foo__
        # str inside ** must start and end with a word character
        # it need for things like "const char *x = (char *)y"
        EMPHASIS_RE = r"(\*)(?!\s+)([^\*^\n]+)(?<!\s)\*"
        STRONG_RE = r"(\*\*)([^\n]+?)\2"
        STRONG_EM_RE = r"(\*\*\*)(?!\s+)([^\*^\n]+)(?<!\s)\*\*\*"
        TEX_RE = r"\B(?<!\$)\$\$(?P<body>[^\n_$](\\\$|[^$\n])*)\$\$(?!\$)\B"
        TIMESTAMP_RE = r"<time:(?P<time>[^>]*?)>"

        # Add inline patterns.  We use a custom numbering of the
        # rules, that preserves the order from upstream but leaves
        # space for us to add our own.
        reg = markdown.util.Registry[markdown.inlinepatterns.Pattern]()
        reg.register(BacktickInlineProcessor(markdown.inlinepatterns.BACKTICK_RE), "backtick", 105)
        reg.register(
            markdown.inlinepatterns.DoubleTagPattern(STRONG_EM_RE, "strong,em"), "strong_em", 100
        )
        reg.register(UserMentionPattern(mention.MENTIONS_RE, self), "usermention", 95)
        reg.register(Tex(TEX_RE, self), "tex", 90)
        reg.register(StreamTopicPattern(get_compiled_stream_topic_link_regex(), self), "topic", 87)
        reg.register(StreamPattern(get_compiled_stream_link_regex(), self), "stream", 85)
        reg.register(Timestamp(TIMESTAMP_RE), "timestamp", 75)
        reg.register(
            UserGroupMentionPattern(mention.USER_GROUP_MENTIONS_RE, self), "usergroupmention", 65
        )
        reg.register(LinkInlineProcessor(markdown.inlinepatterns.LINK_RE, self), "link", 60)
        reg.register(AutoLink(get_web_link_regex(), self), "autolink", 55)
        # Reserve priority 45-54 for linkifiers
        reg = self.register_linkifiers(reg)
        reg.register(
            markdown.inlinepatterns.HtmlInlineProcessor(markdown.inlinepatterns.ENTITY_RE, self),
            "entity",
            40,
        )
        reg.register(markdown.inlinepatterns.SimpleTagPattern(STRONG_RE, "strong"), "strong", 35)
        reg.register(markdown.inlinepatterns.SimpleTagPattern(EMPHASIS_RE, "em"), "emphasis", 30)
        reg.register(markdown.inlinepatterns.SimpleTagPattern(DEL_RE, "del"), "del", 25)
        reg.register(
            markdown.inlinepatterns.SimpleTextInlineProcessor(
                markdown.inlinepatterns.NOT_STRONG_RE
            ),
            "not_strong",
            20,
        )
        reg.register(Emoji(EMOJI_REGEX, self), "emoji", 15)
        reg.register(EmoticonTranslation(EMOTICON_RE, self), "translate_emoticons", 10)
        # We get priority 5 from 'nl2br' extension
        reg.register(UnicodeEmoji(cast(Pattern[str], POSSIBLE_EMOJI_RE), self), "unicodeemoji", 0)
        return reg

    def register_linkifiers(
        self, registry: markdown.util.Registry[markdown.inlinepatterns.Pattern]
    ) -> markdown.util.Registry[markdown.inlinepatterns.Pattern]:
        for linkifier in self.linkifiers:
            pattern = linkifier["pattern"]
            registry.register(
                LinkifierPattern(pattern, linkifier["url_template"], self),
                f"linkifiers/{pattern}",
                45,
            )
        return registry

    def build_treeprocessors(self) -> markdown.util.Registry[markdown.treeprocessors.Treeprocessor]:
        # Here we build all the processors from upstream, plus a few of our own.
        treeprocessors = markdown.util.Registry[markdown.treeprocessors.Treeprocessor]()
        # We get priority 30 from 'hilite' extension
        treeprocessors.register(markdown.treeprocessors.InlineProcessor(self), "inline", 25)
        treeprocessors.register(markdown.treeprocessors.PrettifyTreeprocessor(self), "prettify", 20)
        treeprocessors.register(markdown.treeprocessors.UnescapeTreeprocessor(self), "unescape", 18)
        treeprocessors.register(
            InlineInterestingLinkProcessor(self), "inline_interesting_links", 15
        )
        if settings.CAMO_URI:
            treeprocessors.register(InlineImageProcessor(self), "rewrite_images_proxy", 10)
            treeprocessors.register(InlineVideoProcessor(self), "rewrite_videos_proxy", 10)
        return treeprocessors

    def build_postprocessors(self) -> markdown.util.Registry[markdown.postprocessors.Postprocessor]:
        # These are the default Python-Markdown processors, unmodified.
        postprocessors = markdown.util.Registry[markdown.postprocessors.Postprocessor]()
        postprocessors.register(markdown.postprocessors.RawHtmlPostprocessor(self), "raw_html", 20)
        postprocessors.register(
            markdown.postprocessors.AndSubstitutePostprocessor(), "amp_substitute", 15
        )
        return postprocessors

    def handle_zephyr_mirror(self) -> None:
        if self.linkifiers_key == ZEPHYR_MIRROR_MARKDOWN_KEY:
            # Disable almost all inline patterns for zephyr mirror
            # users' traffic that is mirrored.  Note that
            # inline_interesting_links is a treeprocessor and thus is
            # not removed
            self.inlinePatterns = get_sub_registry(self.inlinePatterns, ["autolink"])
            self.treeprocessors = get_sub_registry(
                self.treeprocessors, ["inline_interesting_links", "rewrite_images_proxy"]
            )
            # insert new 'inline' processor because we have changed self.inlinePatterns
            # but InlineProcessor copies md as self.md in __init__.
            self.treeprocessors.register(
                markdown.treeprocessors.InlineProcessor(self), "inline", 25
            )
            self.preprocessors = get_sub_registry(self.preprocessors, ["custom_text_notifications"])
            self.parser.blockprocessors = get_sub_registry(
                self.parser.blockprocessors, ["paragraph"]
            )


md_engines: Dict[Tuple[int, bool], ZulipMarkdown] = {}
linkifier_data: Dict[int, List[LinkifierDict]] = {}


def make_md_engine(linkifiers_key: int, email_gateway: bool) -> None:
    md_engine_key = (linkifiers_key, email_gateway)
    if md_engine_key in md_engines:
        del md_engines[md_engine_key]

    linkifiers = linkifier_data[linkifiers_key]
    md_engines[md_engine_key] = ZulipMarkdown(
        linkifiers=linkifiers,
        linkifiers_key=linkifiers_key,
        email_gateway=email_gateway,
    )


# Split the topic name into multiple sections so that we can easily use
# our common single link matching regex on it.
basic_link_splitter = re.compile(r"[ !;\),\'\"]")


def percent_escape_format_string(format_string: str) -> str:
    # Find percent-encoded bytes and escape them from the python
    # interpolation.  That is:
    #     %(foo)s -> %(foo)s
    #     %%      -> %%
    #     %ab     -> %%ab
    #     %%ab    -> %%ab
    #     %%%ab   -> %%%%ab
    #
    # We do this here, rather than before storing, to make edits
    # to the underlying linkifier more straightforward, and
    # because JS does not have a real formatter.
    return re.sub(r"(?<!%)(%%)*%([a-fA-F0-9][a-fA-F0-9])", r"\1%%\2", format_string)


@dataclass
class TopicLinkMatch:
    url: str
    text: str
    index: int
    precedence: Optional[int]


# Security note: We don't do any HTML escaping in this
# function on the URLs; they are expected to be HTML-escaped when
# rendered by clients (just as links rendered into message bodies
# are validated and escaped inside `url_to_a`).
def topic_links(linkifiers_key: int, topic_name: str) -> List[Dict[str, str]]:
    matches: List[TopicLinkMatch] = []
    linkifiers = linkifiers_for_realm(linkifiers_key)
    precedence = 0

    options = re2.Options()
    options.log_errors = False
    for linkifier in linkifiers:
        raw_pattern = linkifier["pattern"]
        prepared_url_template = uri_template.URITemplate(linkifier["url_template"])
        try:
            pattern = re2.compile(prepare_linkifier_pattern(raw_pattern), options=options)
        except re2.error:
            # An invalid regex shouldn't be possible here, and logging
            # here on an invalid regex would spam the logs with every
            # message sent; simply move on.
            continue
        pos = 0
        while pos < len(topic_name):
            m = pattern.search(topic_name, pos)
            if m is None:
                break

            match_details = m.groupdict()
            match_text = match_details[OUTER_CAPTURE_GROUP]

            # Adjust the start point of the match for the next
            # iteration -- we rewind the non-word character at the
            # end, if there was one, so a potential next match can
            # also use it.
            pos = m.end() - len(match_details[AFTER_CAPTURE_GROUP])

            # We format the linkifier's url string using the matched text.
            # Also, we include the matched text in the response, so that our clients
            # don't have to implement any logic of their own to get back the text.
            matches += [
                TopicLinkMatch(
                    url=prepared_url_template.expand(**match_details),
                    text=match_text,
                    index=m.start(),
                    precedence=precedence,
                )
            ]
        precedence += 1

    # Sort the matches beforehand so we favor the match with a higher priority and tie-break with the starting index.
    # Note that we sort it before processing the raw URLs so that linkifiers will be prioritized over them.
    matches.sort(key=lambda k: (k.precedence, k.index))

    pos = 0
    # Also make raw URLs navigable.
    while pos < len(topic_name):
        # Assuming that basic_link_splitter matches 1 character,
        # we match segments of the string for URL divided by the matched character.
        next_split = basic_link_splitter.search(topic_name, pos)
        end = next_split.start() if next_split is not None else len(topic_name)
        # We have to match the substring because LINK_REGEX
        # matches the start of the entire string with "^"
        link_match = re.match(get_web_link_regex(), topic_name[pos:end])
        if link_match:
            actual_match_url = link_match.group("url")
            result = urlsplit(actual_match_url)
            if not result.scheme:
                if not result.netloc:
                    i = (result.path + "/").index("/")
                    result = result._replace(netloc=result.path[:i], path=result.path[i:])
                url = result._replace(scheme="https").geturl()
            else:
                url = actual_match_url
            matches.append(
                TopicLinkMatch(
                    url=url,
                    text=actual_match_url,
                    index=pos,
                    precedence=None,
                )
            )
        # Move pass the next split point, and start matching the URL from there
        pos = end + 1

    def are_matches_overlapping(match_a: TopicLinkMatch, match_b: TopicLinkMatch) -> bool:
        return (match_b.index <= match_a.index < match_b.index + len(match_b.text)) or (
            match_a.index <= match_b.index < match_a.index + len(match_a.text)
        )

    # The following removes overlapping intervals depending on the precedence of linkifier patterns.
    # This uses the same algorithm implemented in web/src/markdown.js.
    # To avoid mutating matches inside the loop, the final output gets appended to another list.
    applied_matches: List[TopicLinkMatch] = []
    for current_match in matches:
        # When the current match does not overlap with all existing matches,
        # we are confident that the link should present in the final output because
        #  1. Given that the links are sorted by precedence, the current match has the highest priority
        #     among the matches to be checked.
        #  2. None of the matches with higher priority overlaps with the current match.
        # This might be optimized to search for overlapping matches in O(logn) time,
        # but it is kept as-is since performance is not critical for this codepath and for simplicity.
        if all(
            not are_matches_overlapping(old_match, current_match) for old_match in applied_matches
        ):
            applied_matches.append(current_match)
    # We need to sort applied_matches again because the links were previously ordered by precedence.
    applied_matches.sort(key=lambda v: v.index)
    return [{"url": match.url, "text": match.text} for match in applied_matches]


def maybe_update_markdown_engines(linkifiers_key: int, email_gateway: bool) -> None:
    linkifiers = linkifiers_for_realm(linkifiers_key)
    if linkifiers_key not in linkifier_data or linkifier_data[linkifiers_key] != linkifiers:
        # Linkifier data has changed, update `linkifier_data` and any
        # of the existing Markdown engines using this set of linkifiers.
        linkifier_data[linkifiers_key] = linkifiers
        for email_gateway_flag in [True, False]:
            if (linkifiers_key, email_gateway_flag) in md_engines:
                # Update only existing engines(if any), don't create new one.
                make_md_engine(linkifiers_key, email_gateway_flag)

    if (linkifiers_key, email_gateway) not in md_engines:
        # Markdown engine corresponding to this key doesn't exists so create one.
        make_md_engine(linkifiers_key, email_gateway)


# We want to log Markdown parser failures, but shouldn't log the actual input
# message for privacy reasons.  The compromise is to replace all alphanumeric
# characters with 'x'.
#
# We also use repr() to improve reproducibility, and to escape terminal control
# codes, which can do surprisingly nasty things.
_privacy_re = re.compile(r"\w")


def privacy_clean_markdown(content: str) -> str:
    return repr(_privacy_re.sub("x", content))


def do_convert(
    content: str,
    realm_alert_words_automaton: Optional[ahocorasick.Automaton] = None,
    message: Optional[Message] = None,
    message_realm: Optional[Realm] = None,
    sent_by_bot: bool = False,
    translate_emoticons: bool = False,
    url_embed_data: Optional[Dict[str, Optional[UrlEmbedData]]] = None,
    mention_data: Optional[MentionData] = None,
    email_gateway: bool = False,
    no_previews: bool = False,
) -> MessageRenderingResult:
    """Convert Markdown to HTML, with Zulip-specific settings and hacks."""
    # This logic is a bit convoluted, but the overall goal is to support a range of use cases:
    # * Nothing is passed in other than content -> just run default options (e.g. for docs)
    # * message is passed, but no realm is -> look up realm from message
    # * message_realm is passed -> use that realm for Markdown purposes
    if message is not None and message_realm is None:
        message_realm = message.get_realm()
    if message_realm is None:
        linkifiers_key = DEFAULT_MARKDOWN_KEY
    else:
        linkifiers_key = message_realm.id

    if message and hasattr(message, "id") and message.id:
        logging_message_id = "id# " + str(message.id)
    else:
        logging_message_id = "unknown"

    if (
        message is not None
        and message_realm is not None
        and message_realm.is_zephyr_mirror_realm
        and message.sending_client.name == "zephyr_mirror"
    ):
        # Use slightly customized Markdown processor for content
        # delivered via zephyr_mirror
        linkifiers_key = ZEPHYR_MIRROR_MARKDOWN_KEY

    maybe_update_markdown_engines(linkifiers_key, email_gateway)
    md_engine_key = (linkifiers_key, email_gateway)
    _md_engine = md_engines[md_engine_key]
    # Reset the parser; otherwise it will get slower over time.
    _md_engine.reset()

    # Filters such as UserMentionPattern need a message.
    rendering_result: MessageRenderingResult = MessageRenderingResult(
        rendered_content="",
        mentions_topic_wildcard=False,
        mentions_stream_wildcard=False,
        mentions_user_ids=set(),
        mentions_user_group_ids=set(),
        alert_words=set(),
        links_for_preview=set(),
        user_ids_with_alert_words=set(),
        potential_attachment_path_ids=[],
    )

    _md_engine.zulip_message = message
    _md_engine.zulip_rendering_result = rendering_result
    _md_engine.zulip_realm = message_realm
    _md_engine.zulip_db_data = None  # for now
    _md_engine.image_preview_enabled = image_preview_enabled(message, message_realm, no_previews)
    _md_engine.url_embed_preview_enabled = url_embed_preview_enabled(
        message, message_realm, no_previews
    )
    _md_engine.url_embed_data = url_embed_data

    # Pre-fetch data from the DB that is used in the Markdown thread
    if message_realm is not None:
        # Here we fetch the data structures needed to render
        # mentions/stream mentions from the database, but only
        # if there is syntax in the message that might use them, since
        # the fetches are somewhat expensive and these types of syntax
        # are uncommon enough that it's a useful optimization.

        if mention_data is None:
            mention_backend = MentionBackend(message_realm.id)
            message_sender = None
            if message is not None:
                message_sender = message.sender
            mention_data = MentionData(mention_backend, content, message_sender)

        stream_names = possible_linked_stream_names(content)
        stream_name_info = mention_data.get_stream_name_map(stream_names)

        if content_has_emoji_syntax(content):
            active_realm_emoji = get_name_keyed_dict_for_active_realm_emoji(message_realm.id)
        else:
            active_realm_emoji = {}

        _md_engine.zulip_db_data = DbData(
            realm_alert_words_automaton=realm_alert_words_automaton,
            mention_data=mention_data,
            active_realm_emoji=active_realm_emoji,
            realm_uri=message_realm.uri,
            sent_by_bot=sent_by_bot,
            stream_names=stream_name_info,
            translate_emoticons=translate_emoticons,
        )

    try:
        # Spend at most 5 seconds rendering; this protects the backend
        # from being overloaded by bugs (e.g. Markdown logic that is
        # extremely inefficient in corner cases) as well as user
        # errors (e.g. a linkifier that makes some syntax
        # infinite-loop).
        rendering_result.rendered_content = unsafe_timeout(5, lambda: _md_engine.convert(content))

        # Throw an exception if the content is huge; this protects the
        # rest of the codebase from any bugs where we end up rendering
        # something huge.
        MAX_MESSAGE_LENGTH = settings.MAX_MESSAGE_LENGTH
        if len(rendering_result.rendered_content) > MAX_MESSAGE_LENGTH * 100:
            raise MarkdownRenderingError(
                f"Rendered content exceeds {MAX_MESSAGE_LENGTH * 100} characters (message {logging_message_id})"
            )
        return rendering_result
    except Exception:
        cleaned = privacy_clean_markdown(content)
        markdown_logger.exception(
            "Exception in Markdown parser; input (sanitized) was: %s\n (message %s)",
            cleaned,
            logging_message_id,
        )

        raise MarkdownRenderingError
    finally:
        # These next three lines are slightly paranoid, since
        # we always set these right before actually using the
        # engine, but better safe then sorry.
        _md_engine.zulip_message = None
        _md_engine.zulip_realm = None
        _md_engine.zulip_db_data = None


markdown_time_start = 0.0
markdown_total_time = 0.0
markdown_total_requests = 0


def get_markdown_time() -> float:
    return markdown_total_time


def get_markdown_requests() -> int:
    return markdown_total_requests


def markdown_stats_start() -> None:
    global markdown_time_start
    markdown_time_start = time.time()


def markdown_stats_finish() -> None:
    global markdown_total_time
    global markdown_total_requests
    markdown_total_requests += 1
    markdown_total_time += time.time() - markdown_time_start


def markdown_convert(
    content: str,
    realm_alert_words_automaton: Optional[ahocorasick.Automaton] = None,
    message: Optional[Message] = None,
    message_realm: Optional[Realm] = None,
    sent_by_bot: bool = False,
    translate_emoticons: bool = False,
    url_embed_data: Optional[Dict[str, Optional[UrlEmbedData]]] = None,
    mention_data: Optional[MentionData] = None,
    email_gateway: bool = False,
    no_previews: bool = False,
) -> MessageRenderingResult:
    markdown_stats_start()
    ret = do_convert(
        content,
        realm_alert_words_automaton,
        message,
        message_realm,
        sent_by_bot,
        translate_emoticons,
        url_embed_data,
        mention_data,
        email_gateway,
        no_previews=no_previews,
    )
    markdown_stats_finish()
    return ret


def render_message_markdown(
    message: Message,
    content: str,
    realm: Optional[Realm] = None,
    realm_alert_words_automaton: Optional[ahocorasick.Automaton] = None,
    url_embed_data: Optional[Dict[str, Optional[UrlEmbedData]]] = None,
    mention_data: Optional[MentionData] = None,
    email_gateway: bool = False,
) -> MessageRenderingResult:
    """
    This is basically just a wrapper for do_render_markdown.
    """

    if realm is None:
        realm = message.get_realm()

    sender = message.sender
    sent_by_bot = sender.is_bot
    translate_emoticons = sender.translate_emoticons

    rendering_result = markdown_convert(
        content,
        realm_alert_words_automaton=realm_alert_words_automaton,
        message=message,
        message_realm=realm,
        sent_by_bot=sent_by_bot,
        translate_emoticons=translate_emoticons,
        url_embed_data=url_embed_data,
        mention_data=mention_data,
        email_gateway=email_gateway,
    )

    return rendering_result
