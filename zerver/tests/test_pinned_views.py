from zerver.actions.pinned_views import do_add_pinned_view
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import PinnedView, UserProfile
from zerver.models.pinned_views import LeftSidebarViewLocationEnum


class PinnedViewTests(ZulipTestCase):
    def create_example_pinned_view(self, user: UserProfile) -> str:
        pinned_view = do_add_pinned_view(
            user_profile=user,
            view_id="inbox",
            location=LeftSidebarViewLocationEnum.EXPANDED.value,
            name=None,
            url_hash=None,
        )
        return pinned_view.view_id

    def test_get_pinned_views(self) -> None:
        """Tests fetching pinned views."""
        user = self.example_user("hamlet")
        self.login_user(user)

        result = self.client_get("/json/pinned_views")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["pinned_views"], 0)

        view_id = self.create_example_pinned_view(user)
        result = self.client_get("/json/pinned_views")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["pinned_views"], 1)
        self.assertEqual(view_id, response_dict["pinned_views"][0]["view_id"])

    def test_add_pinned_view(self) -> None:
        """Tests creation of pinned views."""
        user = self.example_user("hamlet")
        self.login_user(user)

        # Test successful creation
        params = {
            "view_id": "recent",
            "location": LeftSidebarViewLocationEnum.EXPANDED.value,
        }
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_success(result)

        # Test invalid view_id
        params["view_id"] = "saved"
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_error(result, "Invalid view_id.")

        # Test invalid location
        params = {
            "view_id": "recent",
            "location": 999,
        }
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_error(result, "Invalid location.")

        # Test duplicate view
        params = {
            "view_id": "recent",
            "location": LeftSidebarViewLocationEnum.EXPANDED.value,
        }
        result = self.client_post("/json/pinned_views", params)
        self.assert_json_error(result, "Pinned view already exists.")

    def test_update_pinned_view_location(self) -> None:
        """Tests updating pinned view location."""
        user = self.example_user("hamlet")
        self.login_user(user)
        view_id = self.create_example_pinned_view(user)

        # Test successful update
        params = {
            "location": LeftSidebarViewLocationEnum.MENU.value,
        }
        result = self.client_patch(f"/json/pinned_views/{view_id}", params)
        self.assert_json_success(result)

        pinned_view = PinnedView.objects.get(user_profile=user, view_id=view_id)
        self.assertEqual(pinned_view.location, LeftSidebarViewLocationEnum.MENU.value)

        # Test nonexistent view
        result = self.client_patch("/json/pinned_views/nonexistent", params)
        self.assert_json_error(result, "Pinned view does not exist.", status_code=404)

        # Test invalid location
        params = {
            "location": 999,
        }
        result = self.client_patch(f"/json/pinned_views/{view_id}", params)
        self.assert_json_error(result, "Invalid location.")

    def test_pinned_view_permissions(self) -> None:
        """Tests permissions for pinned view operations."""
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(othello)

        view_id = self.create_example_pinned_view(hamlet)

        params = {
            "location": LeftSidebarViewLocationEnum.MENU.value,
        }
        result = self.client_patch(f"/json/pinned_views/{view_id}", params)
        self.assert_json_error(result, "Pinned view does not exist.", status_code=404)
