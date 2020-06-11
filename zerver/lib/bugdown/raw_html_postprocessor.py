from markdown.extensions import Extension
from typing import Any
import markdown
import zerver.lib.bugdown.tabbed_sections

class RawHtmlPostprocessor(markdown.postprocessors.RawHtmlPostprocessor):
    def run(self, text: str) -> str:
        processed_text = super().run(text)
        return self.remove_redundant_html(processed_text)

    def remove_redundant_html(self, text: str) -> str:
        text = zerver.lib.bugdown.tabbed_sections.remove_redundant_html(text)
        return text

class RawHtmlPostprocessorExtension(Extension):
    def extendMarkdown(self, md: markdown) -> None:
        md.postprocessors.register(RawHtmlPostprocessor(md), 'raw_html', 30)

def makeExtension(**kwargs: Any) -> RawHtmlPostprocessorExtension:  # pragma: no cover
    return RawHtmlPostprocessorExtension(**kwargs)
