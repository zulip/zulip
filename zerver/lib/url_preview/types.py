from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class UrlEmbedData:
    type: Optional[str] = None
    html: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None

    def merge(self, other: "UrlEmbedData") -> None:
        if self.title is None and other.title is not None:
            self.title = other.title
        if self.description is None and other.description is not None:
            self.description = other.description
        if self.image is None and other.image is not None:
            self.image = other.image
        if self.width is None and other.width is not None:
            self.width = other.width
        if self.height is None and other.height is not None:
            self.height = other.height


@dataclass
class UrlOEmbedData(UrlEmbedData):
    type: Literal["photo", "video"]
    html: Optional[str] = None
