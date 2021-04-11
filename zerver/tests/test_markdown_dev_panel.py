from zerver.lib.test_classes import ZulipTestCase


class TestMarkdownDevPanel(ZulipTestCase):
    def test_get_dev_panel_page(self) -> None:
        # Just to satisfy the test suite.
        target_url = "/devtools/markdown"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)
