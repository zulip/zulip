import os
import re
from re import Match
from xml.etree.ElementTree import Element

from markdown import Extension, Markdown
from markdown.blockparser import BlockParser
from markdown.blockprocessors import BlockProcessor
from typing_extensions import override

from zerver.lib.exceptions import InvalidMarkdownIncludeStatementError
from zerver.lib.markdown.priorities import BLOCK_PROCESSOR_PRIORITIES


class IncludeExtension(Extension):
    def __init__(self, base_path: str) -> None:
        super().__init__()
        self.base_path = base_path

    @override
    def extendMarkdown(self, md: Markdown) -> None:
        md.parser.blockprocessors.register(
            IncludeBlockProcessor(md.parser, self.base_path),
            "include",
            BLOCK_PROCESSOR_PRIORITIES["include"],
        )


class IncludeBlockProcessor(BlockProcessor):
    RE = re.compile(r"^ {,3}\{!([^!]+)!\} *$", re.MULTILINE)

    def __init__(self, parser: BlockParser, base_path: str) -> None:
        super().__init__(parser)
        self.base_path = base_path

    @override
    def test(self, parent: Element, block: str) -> bool:
        return bool(self.RE.search(block))

    def expand_include(self, m: Match[str]) -> str:
        try:
            with open(os.path.normpath(os.path.join(self.base_path, m[1]))) as f:
                lines = f.read().splitlines()
        except OSError as e:
            raise InvalidMarkdownIncludeStatementError(m[0].strip()) from e

        for prep in self.parser.md.preprocessors:
            lines = prep.run(lines)

        return "\n".join(lines)

    @override
    def run(self, parent: Element, blocks: list[str]) -> None:
        self.parser.state.set("include")
        self.parser.parseChunk(parent, self.RE.sub(self.expand_include, blocks.pop(0)))
        self.parser.state.reset()


def makeExtension(base_path: str) -> IncludeExtension:
    return IncludeExtension(base_path=base_path)
