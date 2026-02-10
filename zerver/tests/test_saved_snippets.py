from zerver.actions.saved_snippets import do_create_saved_snippet
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import SavedSnippet, UserProfile


class SavedSnippetTests(ZulipTestCase):
    def create_example_saved_snippet(self, user: UserProfile) -> int:
        saved_snippet = do_create_saved_snippet(
            "Welcome message", "**Welcome** to the organization.", user
        )
        return saved_snippet.id

    def test_create_saved_snippet(self) -> None:
        """Tests creation of saved snippets."""

        user = self.example_user("hamlet")
        self.login_user(user)

        result = self.client_get(
            "/json/saved_snippets",
        )
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["saved_snippets"], 0)

        result = self.client_post(
            "/json/saved_snippets",
            {"title": "Welcome message", "content": "**Welcome** to the organization."},
        )
        response_dict = self.assert_json_success(result)
        saved_snippet_id = response_dict["saved_snippet_id"]

        result = self.client_get(
            "/json/saved_snippets",
        )
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["saved_snippets"], 1)
        self.assertEqual(saved_snippet_id, response_dict["saved_snippets"][0]["id"])

        result = self.client_post(
            "/json/saved_snippets",
            {
                "title": "A" * (SavedSnippet.MAX_TITLE_LENGTH + 60),
                "content": "**Welcome** to the organization.",
            },
        )
        self.assert_json_error(
            result,
            status_code=400,
            msg=f"title is too long (limit: {SavedSnippet.MAX_TITLE_LENGTH} characters)",
        )

    def test_edit_saved_snippet(self) -> None:
        """Tests updation of saved snippets."""

        user = self.example_user("hamlet")
        self.login_user(user)
        saved_snippet_id = self.create_example_saved_snippet(user)

        result = self.client_patch(
            f"/json/saved_snippets/{saved_snippet_id}",
            {"title": "New title"},
        )
        self.assert_json_success(result)

        result = self.client_patch(
            f"/json/saved_snippets/{saved_snippet_id}", {"content": "New content"}
        )
        self.assert_json_success(result)

        # No-op requests succeed.
        result = self.client_patch(
            f"/json/saved_snippets/{saved_snippet_id}",
        )
        self.assert_json_success(result)

        # Tests if error is thrown when the provided ID does not exist.
        result = self.client_patch(
            "/json/saved_snippets/10",
            {"content": "New content"},
        )
        self.assert_json_error(result, "Saved snippet does not exist.", status_code=404)

    def test_delete_saved_snippet(self) -> None:
        """Tests deletion of saved snippets."""

        user = self.example_user("hamlet")
        self.login_user(user)
        saved_snippet_id = self.create_example_saved_snippet(user)

        result = self.client_get(
            "/json/saved_snippets",
        )
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["saved_snippets"], 1)

        result = self.client_delete(
            f"/json/saved_snippets/{saved_snippet_id}",
        )
        self.assert_json_success(result)

        result = self.client_get(
            "/json/saved_snippets",
        )
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["saved_snippets"], 0)

        # Tests if error is thrown when the provided ID does not exist.
        result = self.client_delete(
            "/json/saved_snippets/10",
        )
        self.assert_json_error(result, "Saved snippet does not exist.", status_code=404)
