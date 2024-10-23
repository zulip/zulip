from email.message import EmailMessage

from zerver.lib.url_preview.types import UrlEmbedData


class BaseParser:
    def __init__(self, html_source: bytes, content_type: str | None) -> None:
        # We import BeautifulSoup here, because it's not used by most
        # processes in production, and bs4 is big enough that
        # importing it adds 10s of milliseconds to manage.py startup.
        from bs4 import BeautifulSoup

        m = EmailMessage()
        m["Content-Type"] = content_type
        charset = m.get_content_charset()
        self._soup = BeautifulSoup(html_source, "lxml", from_encoding=charset)

    def extract_data(self) -> UrlEmbedData:
        raise NotImplementedError
