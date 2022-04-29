from typing import Any
from unittest.mock import MagicMock, call, patch

from django.template.loader import get_template
from markdown.extensions.codehilite import makeExtension

from zerver.lib.exceptions import InvalidMarkdownIncludeStatement
from zerver.lib.templates import render_markdown_path
from zerver.lib.test_classes import ZulipTestCase


class TemplateTestCase(ZulipTestCase):
    def test_render_markdown_path(self) -> None:
        ext = makeExtension(
            linenums=None,
            guess_lang=False,
        )
        with patch("zerver.lib.templates.md_extensions", None):
            with patch("markdown.extensions.codehilite.makeExtension", return_value=ext):
                content = render_markdown_path(
                    "zerver/tests/markdown/test_code_hilite.md",
                )

        content_sans_whitespace = content.replace(" ", "").replace("\n", "")
        self.assertEqual(
            content_sans_whitespace,
            '<h1id="hello">Hello!</h1><p>Thisissome<em>boldtext</em>.</p><divclass="codehilite"data-code-language="JavaScript"><pre><span></span><code><spanclass="nx">a</span><spanclass="o">=</span><spanclass="mf">5</span><spanclass="o">+</span><spanclass="mf">5</span><spanclass="p">;</span></code></pre></div><divclass="codehilite"data-code-language="unknown"><pre><span></span><code>a=5+5;</code></pre></div><p><spanclass="tex-error">x\\timesyx\\sdjfhdjfy</span></p><tableclass="codehilitetable"><tr><tdclass="linenos"><divclass="linenodiv"><pre><spanclass="normal">1</span><spanclass="normal">2</span><spanclass="normal">3</span><spanclass="normal">4</span></pre></div></td><tdclass="code"><divclass="codehilite"><pre><span></span><code><spanclass="ch">#!pythonhl_lines=13</span><spanclass="k">def</span><spanclass="nf">foo</span><spanclass="p">():</span><spanclass="n">a</span><spanclass="o">=</span><spanclass="mi">1</span><spanclass="n">b</span><spanclass="o">=</span><spanclass="mi">2</span></code></pre></div></td></tr></table>',
        )

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
  <div class="code-section has-tabs" markdown="1">
    <ul class="nav">
      <li data-language="ios" tabindex="0">iOS</li>
      <li data-language="desktop-web" tabindex="0">Desktop/Web</li>
    </ul>
    <div class="blocks">
      <div data-language="ios" markdown="1"></p>
        <p>iOS instructions</p>
      <p></div>
      <div data-language="desktop-web" markdown="1"></p>
        <p>Desktop/browser instructions</p>
      <p></div>
    </div>
  </div>
</p>

<h2 id="heading-2">Heading 2</h2>
<p>
  <div class="code-section has-tabs" markdown="1">
    <ul class="nav">
      <li data-language="desktop-web" tabindex="0">Desktop/Web</li>
      <li data-language="android" tabindex="0">Android</li>
    </ul>
    <div class="blocks">
      <div data-language="desktop-web" markdown="1"></p>
        <p>Desktop/browser instructions</p>
      <p></div>
      <div data-language="android" markdown="1"></p>
        <p>Android instructions</p>
      <p></div>
    </div>
  </div>
</p>

<h2 id="heading-3">Heading 3</h2>
<p>
  <div class="code-section no-tabs" markdown="1">
    <ul class="nav">
      <li data-language="instructions-for-all-platforms" tabindex="0">Instructions for all platforms</li>
    </ul>
    <div class="blocks">
      <div data-language="instructions-for-all-platforms" markdown="1"></p>
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

    def test_markdown_nested_code_blocks_forced_null(self) -> None:
        def patchfunc(vals: Any) -> Any:
            vals[0].family.grandparent = None
            return vals

        with patch(
            "zerver.lib.markdown.nested_code_blocks.NestedCodeBlocksRendererTreeProcessor.get_nested_code_blocks",
            side_effect=patchfunc,
        ):
            template = get_template("tests/test_markdown.html")
            context = {
                "markdown_test_file": "zerver/tests/markdown/test_nested_code_blocks.md",
            }
            content = template.render(context)
            content_sans_whitespace = content.replace(" ", "").replace("\n", "")
            expected = (
                'header<h1id="this-is-a-heading">Thisisaheading.</h1><ol><li>'
                "<p>Alistitemwithanindentedcodeblock:</p><p><code>indentedcodeblockwithmultiplelines</code></p>"
                '</li></ol><divclass="codehilite"><pre><span></span>'
                "<code>non-indentedcodeblockwithmultiplelines</code></pre></div>footer"
            )
            self.assertEqual(content_sans_whitespace, expected)

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

    @patch("builtins.print")
    def test_custom_markdown_include_extension(self, mock_print: MagicMock) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_custom_include_extension.md",
        }

        with self.assertRaisesRegex(
            InvalidMarkdownIncludeStatement, "Invalid Markdown include statement"
        ):
            template.render(context)
        self.assertEqual(
            mock_print.mock_calls,
            [
                call(
                    "Warning: could not find file templates/zerver/help/include/nonexistent-macro.md. Error: [Errno 2] No such file or directory: 'templates/zerver/help/include/nonexistent-macro.md'"
                )
            ],
        )

    def test_custom_markdown_include_extension_empty_macro(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            "markdown_test_file": "zerver/tests/markdown/test_custom_include_extension_empty.md",
        }
        content = template.render(context)
        content_sans_whitespace = content.replace(" ", "").replace("\n", "")
        expected = "headerfooter"
        self.assertEqual(content_sans_whitespace, expected)
