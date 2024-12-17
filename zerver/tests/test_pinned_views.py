from zerver.actions.pinned_views import do_add_pinned_view, do_get_pinned_views
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile


class PinnedViewTests(ZulipTestCase):
    def create_example_pinned_view(
        self, user: UserProfile, url_hash: str, is_pinned: bool, name: str | None = None
    ) -> str:
        do_add_pinned_view(
            user=user,
            url_hash=url_hash,
            is_pinned=is_pinned,
            name=name,
        )
        return url_hash

    def test_get_pinned_views(self) -> None:
        """Tests fetching pinned views."""
        user = self.example_user("hamlet")
        self.login_user(user)

        result = self.client_get("/json/pinned_views")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["pinned_views"], 0)

        # Test adding a built-in view and fetching it
        self.create_example_pinned_view(user, url_hash="inbox", is_pinned=True)
        result = self.client_get("/json/pinned_views")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["pinned_views"], 1)
        self.assertEqual(response_dict["pinned_views"][0]["url_hash"], "inbox")

    def test_add_pinned_view(self) -> None:
        """Tests creation of pinned views."""
        user = self.example_user("hamlet")
        self.login_user(user)

        # Test successful creation
        params = {
            "url_hash": "recent",
            "is_pinned": "true",
        }
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_success(result)

        # Test name value for builtin views
        params["name"] = "foo"
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_error(result, "Built-in views cannot have a custom name")

        # Test empty url_hash
        params["url_hash"] = ""
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_error(result, "url_hash cannot be blank")

        # Test no name value for custom views
        params = {
            "url_hash": "narrow/view",
            "is_pinned": "true",
        }
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_error(result, "Custom views must have a valid name")

        # Test custom view with name value
        params["name"] = "foo"
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_success(result)

        # Test duplicate view
        new_params = {
            "url_hash": "recent",
            "is_pinned": "true",
        }
        result = self.client_post("/json/pinned_views", new_params)
        self.assert_json_error(result, "Pinned view already exists.")

    def test_update_pinned_view(self) -> None:
        """Tests updating pinned views."""
        user = self.example_user("hamlet")
        self.login_user(user)
        self.create_example_pinned_view(user, url_hash="inbox", is_pinned=True)

        # Test successful update
        params = {
            "is_pinned": "false",
        }
        result = self.client_patch("/json/pinned_views/inbox", params)
        self.assert_json_success(result)

        pinned_views = do_get_pinned_views(user)
        self.assertEqual(pinned_views[0]["is_pinned"], False)

        params = {
            "is_pinned": "true",
            "name": "Inbox View",
        }
        result = self.client_patch("/json/pinned_views/inbox", params)
        self.assert_json_error(result, "Built-in views cannot have a custom name")

        # Test with the name for custom views
        self.create_example_pinned_view(
            user, url_hash="narrow/is/alerted", is_pinned=True, name="Alert Words"
        )
        params = {
            "is_pinned": "false",
            "name": "Watched Phrases",
        }
        result = self.client_patch("/json/pinned_views/narrow/is/alerted", params)
        self.assert_json_success(result)

        # Test nonexistent view
        result = self.client_patch("/json/pinned_views/nonexistent", params)
        self.assert_json_error(result, "Pinned view does not exist.", status_code=404)

    def test_remove_pinned_view(self) -> None:
        """Tests removing pinned views."""
        user = self.example_user("hamlet")
        self.login_user(user)
        self.create_example_pinned_view(user, url_hash="recent", is_pinned=True)

        # Test successful removal
        result = self.client_delete("/json/pinned_views/recent")
        self.assert_json_success(result)

        pinned_views = do_get_pinned_views(user)
        self.assert_length(pinned_views, 0)

        # Test nonexistent view
        result = self.client_delete("/json/pinned_views/nonexistent")
        self.assert_json_error(result, "Pinned view does not exist.", status_code=404)

    def test_pinned_view_permissions(self) -> None:
        """Tests permissions for pinned view operations."""
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(othello)

        self.create_example_pinned_view(hamlet, url_hash="recent", is_pinned=True)

        params = {
            "is_pinned": "false",
        }
        result = self.client_patch("/json/pinned_views/recent", params)
        self.assert_json_error(result, "Pinned view does not exist.", status_code=404)
