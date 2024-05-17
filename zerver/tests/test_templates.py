from django.template.loader import get_template

from zerver.lib.exceptions import InvalidMarkdownIncludeStatementError
from zerver.lib.test_classes import ZulipTestCase


class TemplateTestCase(ZulipTestCase):
    def test_markdown_in_template(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_markdown.md",
        }
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace("\n", "")
        self.assertEqual(
            content_sans_whitespace,
            'header<h1id="hello">Hello!</h1><p>Thisissome<em>boldtext</em>.</p>footer',
        )

    def test_markdown_tabbed_sections_extension(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_tabbed_sections.md",
        }
        content = template.render(context)
        content_sans_whitespace = content.replace(" ", "").replace("\n", "")

        # Note that the expected HTML has a lot of stray <p> tags. This is a
        # consequence of how the Markdown renderer converts newlines to HTML
        # and how elements are delimited by newlines and so forth. However,
        # stray <p> tags are usually matched with closing tags by HTML renderers
        # so this doesn't affect the final rendered UI in any visible way.
        expected_html = """
header

<h1 id="heading">Heading</h1>
<p>
  <div class="tabbed-section has-tabs" markdown="1">
    <ul class="nav">
      <li data-tab-key="ios" tabindex="0">iOS</li>
      <li data-tab-key="desktop-web" tabindex="0">Desktop/Web</li>
    </ul>
    <div class="blocks">
      <div data-tab-key="ios" markdown="1"></p>
        <p>iOS instructions</p>
      <p></div>
      <div data-tab-key="desktop-web" markdown="1"></p>
        <p>Desktop/browser instructions</p>
      <p></div>
    </div>
  </div>
</p>

<h2 id="heading-2">Heading 2</h2>
<p>
  <div class="tabbed-section has-tabs" markdown="1">
    <ul class="nav">
      <li data-tab-key="desktop-web" tabindex="0">Desktop/Web</li>
      <li data-tab-key="android" tabindex="0">Android</li>
    </ul>
    <div class="blocks">
      <div data-tab-key="desktop-web" markdown="1"></p>
        <p>Desktop/browser instructions</p>
      <p></div>
      <div data-tab-key="android" markdown="1"></p>
        <p>Android instructions</p>
      <p></div>
    </div>
  </div>
</p>

<h2 id="heading-3">Heading 3</h2>
<p>
  <div class="tabbed-section no-tabs" markdown="1">
    <ul class="nav">
      <li data-tab-key="instructions-for-all-platforms" tabindex="0">Instructions for all platforms</li>
    </ul>
    <div class="blocks">
      <div data-tab-key="instructions-for-all-platforms" markdown="1"></p>
        <p>Instructions for all platforms</p>
      <p></div>
    </div>
  </div>
</p>

footer
"""

        expected_html_sans_whitespace = expected_html.replace(" ", "").replace("\n", "")
        self.assertEqual(content_sans_whitespace, expected_html_sans_whitespace)

    def test_markdown_tabbed_sections_missing_tabs(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_tabbed_sections_missing_tabs.md",
        }
        expected_regex = "^Tab 'minix' is not present in TAB_SECTION_LABELS in zerver/lib/markdown/tabbed_sections.py$"
        with self.assertRaisesRegex(ValueError, expected_regex):
            template.render(context)

    def test_markdown_nested_code_blocks(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_nested_code_blocks.md",
        }
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace("\n", "")
        expected = (
            'header<h1id="this-is-a-heading">Thisisaheading.</h1><ol>'
            '<li><p>Alistitemwithanindentedcodeblock:</p><divclass="codehilite">'
            "<pre>indentedcodeblockwithmultiplelines</pre></div></li></ol>"
            '<divclass="codehilite"><pre><span></span><code>'
            "non-indentedcodeblockwithmultiplelines</code></pre></div>footer"
        )
        self.assertEqual(content_sans_whitespace, expected)

    def test_custom_markdown_include_extension(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_custom_include_extension.md",
        }

        with self.assertRaisesRegex(
            InvalidMarkdownIncludeStatementError, "Invalid Markdown include statement"
        ):
            template.render(context)

    def test_custom_markdown_include_extension_empty_macro(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_custom_include_extension_empty.md",
        }
        content = template.render(context)
        content_sans_whitespace = content.replace(" ", "").replace("\n", "")
        expected = "headerfooter"
        self.assertEqual(content_sans_whitespace, expected)
