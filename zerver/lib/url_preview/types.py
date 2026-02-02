from dataclasses import dataclass
from typing import Literal


@dataclass
class UrlEmbedData:
    type: str | None = None
    html: str | None = None
    title: str | None = None
    description: str | None = None
    image: str | None = None
    image_width: int | None = None  # nocoverage
    image_height: int | None = None  # nocoverage

    def merge(self, other: "UrlEmbedData") -> None:
        if self.title is None and other.title is not None:
            self.title = other.title
        if self.description is None and other.description is not None:
            self.description = other.description
        if self.image is None and other.image is not None:
            self.image = other.image
        if self.image_width is None and other.image_width is not None:
            self.image_width = other.image_width  # nocoverage
        if self.image_height is None and other.image_height is not None:
            self.image_height = other.image_height  # nocoverage


@dataclass
class UrlOEmbedData(UrlEmbedData):
    type: Literal["photo", "video"]
    html: str | None = None
