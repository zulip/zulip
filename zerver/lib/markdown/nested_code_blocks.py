from collections.abc import Mapping
from typing import Any
from xml.etree.ElementTree import Element, SubElement

import markdown
from markdown.extensions import Extension
from typing_extensions import override

from zerver.lib.markdown import ResultWithFamily, walk_tree_with_family
from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES


class NestedCodeBlocksRenderer(Extension):
    @override
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(
            NestedCodeBlocksRendererTreeProcessor(md, self.getConfigs()),
            "nested_code_blocks",
            PREPROCESSOR_PRIORITIES["nested_code_blocks"],
        )


class NestedCodeBlocksRendererTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, md: markdown.Markdown, config: Mapping[str, Any]) -> None:
        super().__init__(md)

    @override
    def run(self, root: Element) -> None:
        code_tags = walk_tree_with_family(root, self.get_code_tags)
        nested_code_blocks = self.get_nested_code_blocks(code_tags)
        for block in nested_code_blocks:
            tag, text = block.result
            codehilite_block = self.get_codehilite_block(text)
            self.replace_element(block.family.grandparent, codehilite_block, block.family.parent)

    def get_code_tags(self, e: Element) -> tuple[str, str | None] | None:
        if e.tag == "code":
            return (e.tag, e.text)
        return None

    def get_nested_code_blocks(
        self,
        code_tags: list[ResultWithFamily[tuple[str, str | None]]],
    ) -> list[ResultWithFamily[tuple[str, str | None]]]:
        nested_code_blocks = []
        for code_tag in code_tags:
            parent: Any = code_tag.family.parent
            grandparent: Any = code_tag.family.grandparent
            if (
                parent.tag == "p"
                and grandparent.tag == "li"
                and parent.text is None
                and len(parent) == 1
                and sum(1 for text in parent.itertext()) == 1
            ):
                # if the parent (<p>) has no text, and no children,
                # that means that the <code> element inside is its
                # only thing inside the bullet, we can confidently say
                # that this is a nested code block
                nested_code_blocks.append(code_tag)

        return nested_code_blocks

    def get_codehilite_block(self, code_block_text: str | None) -> Element:
        div = Element("div")
        div.set("class", "codehilite")
        pre = SubElement(div, "pre")
        pre.text = code_block_text
        return div

    def replace_element(
        self,
        parent: Element | None,
        replacement: Element,
        element_to_replace: Element,
    ) -> None:
        if parent is None:
            return

        for index, child in enumerate(parent):
            if child is element_to_replace:
                parent.insert(index, replacement)
                parent.remove(element_to_replace)


def makeExtension(*args: Any, **kwargs: str) -> NestedCodeBlocksRenderer:
    return NestedCodeBlocksRenderer(**kwargs)
