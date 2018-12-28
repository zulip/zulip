import mock
from zerver.lib.test_classes import ZulipTestCase
from typing import Dict

class TestFeedbackBot(ZulipTestCase):
    def setUp(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email, realm=user_profile.realm)

    def test_create_video_call_success(self) -> None:
        with mock.patch('zerver.lib.actions.request_zoom_video_call_url', return_value={'join_url': 'example.com'}):
            result = self.client_get("/json/calls/create")
            self.assert_json_success(result)
            self.assertEqual(200, result.status_code)
            content = result.json()
            self.assertEqual(content['zoom_url'], 'example.com')

    def test_create_video_call_failure(self) -> None:
        with mock.patch('zerver.lib.actions.request_zoom_video_call_url', return_value=None):
            result = self.client_get("/json/calls/create")
            self.assert_json_success(result)
            self.assertEqual(200, result.status_code)
            content = result.json()
            self.assertEqual(content['zoom_url'], '')

    def test_create_video_request_success(self) -> None:
        class MockResponse:
            def __init__(self) -> None:
                self.status_code = 200

            def json(self) -> Dict[str, str]:
                return {"join_url": "example.com"}

        with mock.patch('requests.post', return_value=MockResponse()):
            result = self.client_get("/json/calls/create")
            self.assert_json_success(result)

    def test_create_video_request(self) -> None:
        with mock.patch('requests.post'):
            result = self.client_get("/json/calls/create")
            self.assert_json_success(result)
