from typing import Any

class BaseParser:
    def __init__(self, html_source: str) -> None:
        # We import BeautifulSoup here, because it's not used by most
        # processes in production, and bs4 is big enough that
        # importing it adds 10s of milliseconds to manage.py startup.
        from bs4 import BeautifulSoup
        self._soup = BeautifulSoup(html_source, "lxml")

    def extract_data(self) -> Any:
        raise NotImplementedError()
