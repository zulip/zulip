import orjson

from zerver.lib.test_classes import ZulipTestCase


class TestMarkdownDevPanel(ZulipTestCase):
    def test_get_dev_panel_page(self) -> None:
        # Just to satisfy the test suite.
        target_url = "/devtools/markdown"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)

    def test_get_fixtures_for_success(self) -> None:
        target_url = "/devtools/markdown/edge_case_embedded_link_inside_Italic/fixture"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(orjson.loads(response.content)["test_input"])

    def test_get_markdown_fixture_for_nonexistant_fixture(self) -> None:
        target_url = "/devtools/markdown/somerandomnonexistantmarkdownfixture/fixture"
        response = self.client_get(target_url)
        expected_response = {
            "msg": 'Markdown fixture with name: "somerandomnonexistantmarkdownfixture" not found!',
            "result": "error",
        }
        self.assertEqual(response.status_code, 404)
        self.assertEqual(orjson.loads(response.content), expected_response)
