from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import make_mock_request


class MakeMockRequestTest(ZulipTestCase):
    def test_basic_get_request(self) -> None:
        request = make_mock_request(method="GET", path="/basic")
        self.assertEqual(request.method, "GET")

    def test_post_with_data_and_headers(self) -> None:
        request = make_mock_request(
            method="POST",
            path="/submit",
            data={"key": "value"},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.POST["key"], "value")
        self.assertIn("HTTP_CONTENT_TYPE", request.META)

    def test_with_user_and_files(self) -> None:
        user = self.example_user("hamlet")
        files = {"file": b"content"}
        request = make_mock_request(method="POST", path="/upload", user=user, files=files)
        self.assertEqual(request.user, user)
        self.assertEqual(getattr(request, "realm", None), user.realm)
        self.assertIn("file", request.FILES)

    def test_without_user_sets_realm_none(self) -> None:
        request = make_mock_request(method="GET", path="/no_user")
        # realm deve ser None quando não há usuário
        self.assertFalse(hasattr(request, "user"))
        self.assertIsNone(getattr(request, "realm", None))

    def test_make_mock_request_without_user(self) -> None:
        # Teste redundante para garantir cobertura total do else
        request = make_mock_request(method="GET", path="/else_case")
        self.assertIsNone(getattr(request, "realm", None))
