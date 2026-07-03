import warnings

from zerver.lib.markdown.from_html import convert_html_to_markdown
from zerver.lib.test_classes import ZulipTestCase


class ConvertHTMLToMarkdownTest(ZulipTestCase):
    def test_real_html(self) -> None:
        self.assertEqual(convert_html_to_markdown("<p>Hello <b>world</b></p>"), "Hello **world**")

    def test_atx_headings(self) -> None:
        # Zulip's Markdown renderer does not support Setext-style headings.
        self.assertEqual(convert_html_to_markdown("<h1>Title</h1>"), "# Title")

    def test_url_like_content_is_left_unchanged(self) -> None:
        # Message content is often a bare URL. BeautifulSoup emits
        # MarkupResemblesLocatorWarning for such input, which becomes fatal
        # under the PYTHONWARNINGS=error policy used in CI, so
        # convert_html_to_markdown suppresses it. Promote warnings to errors
        # here so this test fails deterministically (not only in CI) if that
        # suppression is removed.
        url = "https://www.youtube.com/watch?v=MRmGDhlMhNA"
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(convert_html_to_markdown(url), url)
