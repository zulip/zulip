from zerver.lib.avatar import avatar_url
from zerver.lib.test_classes import UploadSerializeMixin, ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file
from zerver.models import UserProfile


class AdminAvatarTest(UploadSerializeMixin, ZulipTestCase):
    def test_admin_set_user_avatar(self) -> None:
        self.login("iago")
        cordelia = self.example_user("cordelia")
        with get_test_image_file("img.png") as fp:
            result = self.client_post(f"/json/users/{cordelia.id}/avatar", {"file": fp})

        self.assert_json_success(result)
        cordelia.refresh_from_db()
        self.assertEqual(cordelia.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(cordelia.avatar_version > 1)

    def test_non_admin_set_user_avatar(self) -> None:
        self.login("hamlet")
        cordelia = self.example_user("cordelia")
        with get_test_image_file("img.png") as fp:
            result = self.client_post(f"/json/users/{cordelia.id}/avatar", {"file": fp})
        self.assert_json_error(result, "Insufficient permission")

    def test_admin_set_user_avatar_invalid_file(self) -> None:
        self.login("iago")
        cordelia = self.example_user("cordelia")
        with get_test_image_file("text.txt") as fp:
            result = self.client_post(f"/json/users/{cordelia.id}/avatar", {"file": fp})
        self.assert_json_error(result, "Invalid image format")

    def test_admin_delete_user_avatar(self) -> None:
        self.login("iago")
        cordelia = self.example_user("cordelia")

        # Ensure user has a custom avatar first
        with get_test_image_file("img.png") as fp:
            self.client_post(f"/json/users/{cordelia.id}/avatar", {"file": fp})

        cordelia.refresh_from_db()
        self.assertEqual(cordelia.avatar_source, UserProfile.AVATAR_FROM_USER)

        result = self.client_delete(f"/json/users/{cordelia.id}/avatar")
        self.assert_json_success(result)

        cordelia.refresh_from_db()
        self.assertEqual(cordelia.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        response_json = self.assert_json_success(result)
        self.assertEqual(response_json["avatar_url"], avatar_url(cordelia))

    def test_non_admin_delete_user_avatar(self) -> None:
        self.login("hamlet")
        cordelia = self.example_user("cordelia")
        result = self.client_delete(f"/json/users/{cordelia.id}/avatar")
        self.assert_json_error(result, "Insufficient permission")

    def test_admin_set_user_avatar_multiple_files(self) -> None:
        self.login("iago")
        cordelia = self.example_user("cordelia")
        with get_test_image_file("img.png") as fp1, get_test_image_file("img.png") as fp2:
            result = self.client_post(
                f"/json/users/{cordelia.id}/avatar",
                {"file1": fp1, "file2": fp2},
            )
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_admin_set_user_avatar_too_large(self) -> None:
        self.login("iago")
        cordelia = self.example_user("cordelia")
        with get_test_image_file("img.png") as fp, self.settings(MAX_AVATAR_FILE_SIZE_MIB=0):
            result = self.client_post(f"/json/users/{cordelia.id}/avatar", {"file": fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MiB")

    def test_bot_owner_set_user_avatar_errors(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        cordelia.is_bot = True
        cordelia.bot_owner = hamlet
        cordelia.save()

        with get_test_image_file("img.png") as fp:
            result = self.client_post(f"/json/users/{cordelia.id}/avatar", {"file": fp})
        self.assert_json_error(result, "Must be an organization administrator")

        result = self.client_delete(f"/json/users/{cordelia.id}/avatar")
        self.assert_json_error(result, "Must be an organization administrator")
