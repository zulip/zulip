from zerver.actions.navigation_views import do_add_navigation_view
from zerver.lib.navigation_views import get_navigation_views_for_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile


class NavigationViewTests(ZulipTestCase):
    def create_example_navigation_view(
        self, user: UserProfile, fragment: str, is_pinned: bool, name: str | None = None
    ) -> str:
        do_add_navigation_view(
            user,
            fragment,
            is_pinned,
            name,
        )
        return fragment

    def test_get_navigation_views(self) -> None:
        """Tests fetching navigation views."""
        user = self.example_user("hamlet")
        self.login_user(user)

        result = self.client_get("/json/navigation_views")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["navigation_views"], 0)

        # Test adding a built-in view and fetching it
        self.create_example_navigation_view(user, fragment="inbox", is_pinned=True)
        result = self.client_get("/json/navigation_views")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["navigation_views"], 1)
        self.assertEqual(response_dict["navigation_views"][0]["fragment"], "inbox")
        self.assertEqual(response_dict["navigation_views"][0]["is_pinned"], True)

    def test_add_navigation_view(self) -> None:
        """Tests creation of navigation views."""
        user = self.example_user("hamlet")
        self.login_user(user)

        # Test successful creation
        params = {
            "fragment": "recent",
            "is_pinned": "true",
        }
        result = self.client_post("/json/navigation_views", params)
        self.assert_json_success(result)

        # Test name value for builtin views
        params["name"] = "foo"
        result = self.client_post("/json/navigation_views", params)
        self.assert_json_error(result, "Built-in views cannot have a custom name.")

        # Test empty fragment
        params["fragment"] = ""
        result = self.client_post("/json/navigation_views", params)
        self.assert_json_error(result, "fragment cannot be blank")

        # Test no name value for custom views
        params = {
            "fragment": "narrow/view",
            "is_pinned": "true",
        }
        result = self.client_post("/json/navigation_views", params)
        self.assert_json_error(result, "Custom views must have a valid name.")

        # Test custom view with name value
        params["name"] = "foo"
        result = self.client_post("/json/navigation_views", params)
        self.assert_json_success(result)

        # Test duplicate view
        new_params = {
            "fragment": "recent",
            "is_pinned": "true",
        }
        result = self.client_post("/json/navigation_views", new_params)
        self.assert_json_error(result, "Navigation view already exists.")

        # Test duplicate view by name
        new_params = {
            "fragment": "narorw/is/attachment",
            "is_pinned": "true",
            "name": "foo",
        }
        result = self.client_post("/json/navigation_views", new_params)
        self.assert_json_error(result, "Navigation view already exists.")

    def test_update_navigation_view(self) -> None:
        """Tests updating navigation views."""
        user = self.example_user("hamlet")
        self.login_user(user)
        self.create_example_navigation_view(user, fragment="inbox", is_pinned=True)

        # Test successful update
        params = {
            "is_pinned": "false",
        }
        result = self.client_patch("/json/navigation_views/inbox", params)
        self.assert_json_success(result)

        navigation_views = get_navigation_views_for_user(user)
        self.assertEqual(navigation_views[0]["is_pinned"], False)

        params = {
            "is_pinned": "true",
            "name": "Inbox View",
        }
        result = self.client_patch("/json/navigation_views/inbox", params)
        self.assert_json_error(result, "Built-in views cannot have a custom name.")

        # Test with the name for custom views
        self.create_example_navigation_view(
            user, fragment="narrow/is/alerted", is_pinned=True, name="Alert Words"
        )
        params = {
            "is_pinned": "false",
            "name": "Watched Phrases",
        }
        result = self.client_patch("/json/navigation_views/narrow/is/alerted", params)
        self.assert_json_success(result)

        self.create_example_navigation_view(
            user, fragment="narrow/is/attachment", is_pinned=True, name="Attachments"
        )
        params = {
            "is_pinned": "false",
            "name": "Watched Phrases",
        }
        result = self.client_patch("/json/navigation_views/narrow/is/attachment", params)
        self.assert_json_error(result, "Navigation view already exists.")

        params = {
            "is_pinned": "false",
            "name": "New view",
        }
        # Test nonexistent view
        result = self.client_patch("/json/navigation_views/nonexistent", params)
        self.assert_json_error(result, "Navigation view does not exist.", status_code=404)

    def test_remove_navigation_view(self) -> None:
        """Tests removing navigation views."""
        user = self.example_user("hamlet")
        self.login_user(user)
        self.create_example_navigation_view(user, fragment="recent", is_pinned=True)

        # Test successful removal
        result = self.client_delete("/json/navigation_views/recent")
        self.assert_json_success(result)

        navigation_views = get_navigation_views_for_user(user)
        self.assert_length(navigation_views, 0)

        # Test nonexistent view
        result = self.client_delete("/json/navigation_views/nonexistent")
        self.assert_json_error(result, "Navigation view does not exist.", status_code=404)

    def test_navigation_view_permissions(self) -> None:
        """Tests permissions for navigation view operations."""
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(othello)

        self.create_example_navigation_view(hamlet, fragment="recent", is_pinned=True)

        params = {
            "is_pinned": "false",
        }
        result = self.client_patch("/json/navigation_views/recent", params)
        self.assert_json_error(result, "Navigation view does not exist.", status_code=404)
