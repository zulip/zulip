from typing import Any
from bs4 import BeautifulSoup


class BaseParser:
    def __init__(self, html_source: str) -> None:
        self._soup = BeautifulSoup(html_source, "lxml")

    def extract_data(self) -> Any:
        raise NotImplementedError()
