from typing import Any, Text
from bs4 import BeautifulSoup


class BaseParser:
    def __init__(self, html_source: Text) -> None:
        self._soup = BeautifulSoup(html_source, "lxml")

    def extract_data(self) -> Any:
        raise NotImplementedError()
