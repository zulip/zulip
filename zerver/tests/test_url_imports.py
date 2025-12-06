"""
Tests for URL module imports and route resolution.

This test file validates that all URL modules import without errors
and that URL reversing works for representative named routes.
"""

from django.urls import reverse

from zerver.lib.test_classes import ZulipTestCase


class URLImportTest(ZulipTestCase):
    """Test that all URL modules can be imported without ImportError."""

    def test_zproject_urls_import(self) -> None:
        """Test that zproject.urls imports without error."""
        # This import will fail if any view module referenced in urls.py is missing
        from zproject import urls

        self.assertIsNotNone(urls.urlpatterns)

    def test_analytics_urls_import(self) -> None:
        """Test that analytics.urls imports without error."""
        from analytics import urls

        self.assertIsNotNone(urls.urlpatterns)

    def test_zproject_dev_urls_import(self) -> None:
        """Test that zproject.dev_urls imports without error."""
        from zproject import dev_urls

        self.assertIsNotNone(dev_urls.urls)

    def test_zilencer_urls_import(self) -> None:
        """Test that zilencer.urls imports without error."""
        from zilencer import urls

        self.assertIsNotNone(urls.urlpatterns)

    def test_corporate_urls_import(self) -> None:
        """Test that corporate.urls imports without error."""
        from corporate import urls

        self.assertIsNotNone(urls.urlpatterns)


class URLReverseTest(ZulipTestCase):
    """Test that URL reversing works for representative named routes."""

    def test_reverse_home(self) -> None:
        """Test reversing the home URL."""
        url = reverse("home")
        self.assertEqual(url, "/")

    def test_reverse_login(self) -> None:
        """Test reversing the login URL."""
        url = reverse("login")
        self.assertIn("login", url)

    def test_reverse_server_time(self) -> None:
        """Test reversing the server_time URL."""
        url = reverse("server_time")
        self.assertEqual(url, "/server/server_time")

    def test_reverse_stats(self) -> None:
        """Test reversing the stats URL."""
        url = reverse("stats")
        self.assertIn("stats", url)


class ServerTimeEndpointTest(ZulipTestCase):
    """Test the server_time endpoint for URL coverage."""

    def test_server_time_endpoint(self) -> None:
        """Test that the server/server_time endpoint returns valid JSON with timestamp."""
        result = self.client_get("/server/server_time")
        response_dict = self.assert_json_success(result)
        self.assertIn("server_timestamp", response_dict)
        self.assertIsInstance(response_dict["server_timestamp"], float)
