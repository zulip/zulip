import re
from unittest import mock

from lxml import etree

from corporate.urls import landing_page_urls
from corporate.views.sitemap import EXCLUDED_LANDING_PAGE_PATHS, SITEMAP_NAMESPACE
from zerver.lib.test_classes import ZulipTestCase


class SitemapTest(ZulipTestCase):
    def get_sitemap_urls(self) -> list[str]:
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True, POLICIES_DIRECTORY="corporate/policies"):
            result = self.client_get("/sitemap.xml", subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Content-Type"], "application/xml")

        urlset = etree.fromstring(result.content)
        self.assertEqual(urlset.tag, f"{{{SITEMAP_NAMESPACE}}}urlset")
        urls = []
        for loc in urlset.iter(f"{{{SITEMAP_NAMESPACE}}}loc"):
            assert loc.text is not None
            urls.append(loc.text)
        return urls

    def test_sitemap_only_on_zulip_com(self) -> None:
        result = self.client_get("/sitemap.xml", subdomain="")
        self.assertEqual(result.status_code, 404)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/sitemap.xml", subdomain="zulip")
        self.assertEqual(result.status_code, 404)

    def test_sitemap_contents(self) -> None:
        urls = self.get_sitemap_urls()
        self.assert_length(set(urls), len(urls))
        for url in urls:
            self.assertTrue(url.startswith("https://zulip.com/"))

        for path in [
            "/",
            "/jobs/",
            "/plans/",
            "/case-studies/tum/",
            "/help/",
            "/help/star-a-message",
            "/api/",
            "/api/send-message",
            "/integrations/",
            "/integrations/category/communication",
            "/integrations/github",
            "/policies/",
            "/policies/terms",
        ]:
            self.assertIn(f"https://zulip.com{path}", urls)

        for path in [
            "/hello/",
            "/attribution/",
            "/help/missing",
            "/policies/missing",
            # Variants of /apps/ and redirects to other pages.
            "/apps/download/linux",
            "/apps/linux",
            "/for/companies/",
        ]:
            self.assertNotIn(f"https://zulip.com{path}", urls)

    def test_excluded_landing_pages_exist(self) -> None:
        landing_page_paths = {f"/{url_pattern.pattern}" for url_pattern in landing_page_urls}
        self.assertLessEqual(EXCLUDED_LANDING_PAGE_PATHS, landing_page_paths)

    def test_sitemap_pages_are_indexable(self) -> None:
        # The help center is served by nginx, so we can't fetch it here.
        paths = [
            url.removeprefix("https://zulip.com")
            for url in self.get_sitemap_urls()
            if not url.startswith("https://zulip.com/help/")
        ]
        canonical_link_regex = re.compile(r'<link rel="canonical" href="([^"]*)" />')

        # Mock OpenGraph description generation purely to speed up these tests.
        with (
            mock.patch("zerver.lib.html_to_text.html_to_text", return_value="Description"),
            self.settings(ROOT_DOMAIN_LANDING_PAGE=True, POLICIES_DIRECTORY="corporate/policies"),
        ):
            for path in paths:
                result = self.client_get(path, subdomain="")
                self.assertEqual(result.status_code, 200, path)
                content = result.content.decode()
                self.assertNotIn('<meta name="robots" content="noindex,nofollow" />', content)
                canonical_link = canonical_link_regex.search(content)
                if canonical_link is not None:
                    self.assertEqual(canonical_link[1], f"https://zulip.com{path}")
