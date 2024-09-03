from typing import Any
from xml.etree.ElementTree import Element

import markdown
from django.contrib.staticfiles.storage import staticfiles_storage
from markdown.extensions import Extension
from typing_extensions import override

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES


class MarkdownStaticImagesGenerator(Extension):
    @override
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(
            StaticImageProcessor(md),
            "static_images",
            PREPROCESSOR_PRIORITIES["static_images"],
        )


class StaticImageProcessor(markdown.treeprocessors.Treeprocessor):
    """
    Rewrite img tags which refer to /static/ to use staticfiles
    """

    @override
    def run(self, root: Element) -> None:
        for img in root.iter("img"):
            url = img.get("src")
            if url is not None and url.startswith("/static/"):
                img.set("src", staticfiles_storage.url(url.removeprefix("/static/")))


def makeExtension(*args: Any, **kwargs: str) -> MarkdownStaticImagesGenerator:
    return MarkdownStaticImagesGenerator(*args, **kwargs)
