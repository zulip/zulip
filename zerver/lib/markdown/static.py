from typing import Any
from xml.etree.ElementTree import Element

import markdown
from django.contrib.staticfiles.storage import staticfiles_storage
from markdown.extensions import Extension

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITES


class MarkdownStaticImagesGenerator(Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(
            StaticImageProcessor(md),
            "static_images",
            PREPROCESSOR_PRIORITES["static_images"],
        )


class StaticImageProcessor(markdown.treeprocessors.Treeprocessor):
    """
    Rewrite img tags which refer to /static/ to use staticfiles
    """

    def run(self, root: Element) -> None:
        for img in root.iter("img"):
            url = img.get("src")
            if url is not None and url.startswith("/static/"):
                img.set("src", staticfiles_storage.url(url[len("/static/") :]))


def makeExtension(*args: Any, **kwargs: str) -> MarkdownStaticImagesGenerator:
    return MarkdownStaticImagesGenerator(*args, **kwargs)
