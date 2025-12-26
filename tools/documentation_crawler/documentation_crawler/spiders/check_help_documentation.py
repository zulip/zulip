from typing_extensions import override

from .common.spiders import BaseDocumentationSpider


class HelpDocumentationSpider(BaseDocumentationSpider):
    name = "help_documentation_crawler"
    start_urls = ["http://localhost:9981/help"]
    deny_domains: list[str] = []
    deny = ["/policies/privacy"]

    @override
    def _is_external_url(self, url: str) -> bool:
        return not f"{url}/".startswith("http://localhost:9981/help/") or self._has_extension(url)


class APIDocumentationSpider(BaseDocumentationSpider):
    name = "api_documentation_crawler"
    start_urls = ["http://localhost:9981/api"]
    deny_domains: list[str] = []

    @override
    def _is_external_url(self, url: str) -> bool:
        return not f"{url}/".startswith("http://localhost:9981/api") or self._has_extension(url)


class PorticoDocumentationSpider(BaseDocumentationSpider):
    @override
    def _is_external_url(self, url: str) -> bool:
        return (
            not url.startswith("http://localhost:9981")
            or url.startswith(("http://localhost:9981/help", "http://localhost:9981/api"))
            or self._has_extension(url)
        )

    name = "portico_documentation_crawler"
    start_urls = [
        "http://localhost:9981/hello/",
        "http://localhost:9981/history/",
        "http://localhost:9981/plans/",
        "http://localhost:9981/team/",
        "http://localhost:9981/apps/",
        "http://localhost:9981/integrations/",
        "http://localhost:9981/policies/terms",
        "http://localhost:9981/policies/privacy",
        "http://localhost:9981/features/",
        "http://localhost:9981/why-zulip/",
        "http://localhost:9981/for/open-source/",
        "http://localhost:9981/for/business/",
        "http://localhost:9981/for/communities/",
        "http://localhost:9981/for/research/",
        "http://localhost:9981/security/",
    ]
    deny_domains: list[str] = []
