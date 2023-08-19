from unittest import mock

from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_create_user
from zerver.actions.realm_emoji import check_add_realm_emoji
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.users import do_change_user_role
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file
from zerver.lib.upload.base import BadImageError
from zerver.models import Realm, RealmEmoji, UserProfile, get_realm


class RealmEmojiTest(ZulipTestCase):
    def create_test_emoji(self, name: str, author: UserProfile) -> RealmEmoji:
        with get_test_image_file("img.png") as img_file:
            realm_emoji = check_add_realm_emoji(
                realm=author.realm, name=name, author=author, image_file=img_file
            )
            if realm_emoji is None:
                raise Exception("Error creating test emoji.")  # nocoverage
        return realm_emoji

    def create_test_emoji_with_no_author(self, name: str, realm: Realm) -> RealmEmoji:
        realm_emoji = RealmEmoji.objects.create(realm=realm, name=name, file_name=name)
        return realm_emoji

    def test_list(self) -> None:
        emoji_author = self.example_user("iago")
        self.login_user(emoji_author)
        self.create_test_emoji("my_emoji", emoji_author)

        result = self.client_get("/json/realm/emoji")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["emoji"], 2)

    def test_list_no_author(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        realm_emoji = self.create_test_emoji_with_no_author("my_emoji", realm)

        result = self.client_get("/json/realm/emoji")
        content = self.assert_json_success(result)
        self.assert_length(content["emoji"], 2)
        test_emoji = content["emoji"][str(realm_emoji.id)]
        self.assertIsNone(test_emoji["author_id"])

    def test_list_admins_only(self) -> None:
        # Test that realm emoji list is public and realm emojis
        # having no author are also there in the list.
        self.login("othello")
        realm = get_realm("zulip")
        realm.add_custom_emoji_policy = Realm.POLICY_ADMINS_ONLY
        realm.save()
        realm_emoji = self.create_test_emoji_with_no_author("my_emoji", realm)

        result = self.client_get("/json/realm/emoji")
        content = self.assert_json_success(result)
        self.assert_length(content["emoji"], 2)
        test_emoji = content["emoji"][str(realm_emoji.id)]
        self.assertIsNone(test_emoji["author_id"])

    def test_upload(self) -> None:
        user = self.example_user("iago")
        email = user.email
        self.login_user(user)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji", info=emoji_data)
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        realm_emoji = RealmEmoji.objects.get(name="my_emoji")
        assert realm_emoji.author is not None
        self.assertEqual(realm_emoji.author.email, email)

        result = self.client_get("/json/realm/emoji")
        content = self.assert_json_success(result)
        self.assert_length(content["emoji"], 2)
        test_emoji = content["emoji"][str(realm_emoji.id)]
        self.assertIn("author_id", test_emoji)
        author = UserProfile.objects.get(id=test_emoji["author_id"])
        self.assertEqual(author.email, email)

    def test_override_built_in_emoji_by_admin(self) -> None:
        # Test that only administrators can override built-in emoji.
        self.login("othello")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/laughing", info=emoji_data)
        self.assert_json_error(
            result,
            "Only administrators can override default emoji.",
        )

        user = self.example_user("iago")
        email = user.email
        self.login_user(user)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/smile", info=emoji_data)
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        realm_emoji = RealmEmoji.objects.get(name="smile")
        assert realm_emoji.author is not None
        self.assertEqual(realm_emoji.author.email, email)

    def test_realm_emoji_repr(self) -> None:
        realm_emoji = RealmEmoji.objects.get(name="green_tick")
        file_name = str(realm_emoji.id) + ".png"
        self.assertEqual(
            repr(realm_emoji),
            f"<RealmEmoji: zulip: {realm_emoji.id} green_tick False {file_name}>",
        )

    def test_upload_exception(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_em*oji", info=emoji_data)
        self.assert_json_error(
            result,
            "Emoji names must contain only lowercase English letters, digits, spaces, dashes, and underscores.",
        )

    def test_forward_slash_exception(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post(
                "/json/realm/emoji/my/emoji/with/forward/slash/", info=emoji_data
            )
        self.assert_json_error(
            result,
            "Emoji names must contain only lowercase English letters, digits, spaces, dashes, and underscores.",
        )

    def test_upload_uppercase_exception(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_EMoji", info=emoji_data)
        self.assert_json_error(
            result,
            "Emoji names must contain only lowercase English letters, digits, spaces, dashes, and underscores.",
        )

    def test_upload_end_character_exception(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_", info=emoji_data)
        self.assert_json_error(result, "Emoji names must end with either a letter or digit.")

    def test_missing_name_exception(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/%20", info=emoji_data)
        self.assert_json_error(result, "Emoji name is missing")

    def test_can_add_custom_emoji(self) -> None:
        def validation_func(user_profile: UserProfile) -> bool:
            return user_profile.can_add_custom_emoji()

        self.check_has_permission_policies("add_custom_emoji_policy", validation_func)

    def test_user_settings_for_adding_custom_emoji(self) -> None:
        othello = self.example_user("othello")
        self.login_user(othello)

        do_change_user_role(othello, UserProfile.ROLE_MODERATOR, acting_user=None)
        do_set_realm_property(
            othello.realm, "add_custom_emoji_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_1", info=emoji_data)
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_role(othello, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_1", info=emoji_data)
        self.assert_json_success(result)

        do_set_realm_property(
            othello.realm, "add_custom_emoji_policy", Realm.POLICY_MODERATORS_ONLY, acting_user=None
        )
        do_change_user_role(othello, UserProfile.ROLE_MEMBER, acting_user=None)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_2", info=emoji_data)
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_role(othello, UserProfile.ROLE_MODERATOR, acting_user=None)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_2", info=emoji_data)
        self.assert_json_success(result)

        do_set_realm_property(
            othello.realm,
            "add_custom_emoji_policy",
            Realm.POLICY_FULL_MEMBERS_ONLY,
            acting_user=None,
        )
        do_set_realm_property(othello.realm, "waiting_period_threshold", 100000, acting_user=None)
        do_change_user_role(othello, UserProfile.ROLE_MEMBER, acting_user=None)

        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_3", info=emoji_data)
        self.assert_json_error(result, "Insufficient permission")

        do_set_realm_property(othello.realm, "waiting_period_threshold", 0, acting_user=None)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_3", info=emoji_data)
        self.assert_json_success(result)

        do_set_realm_property(
            othello.realm, "add_custom_emoji_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )
        do_change_user_role(othello, UserProfile.ROLE_GUEST, acting_user=None)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_4", info=emoji_data)
        self.assert_json_error(result, "Not allowed for guest users")

        do_change_user_role(othello, UserProfile.ROLE_MEMBER, acting_user=None)
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji_4", info=emoji_data)
        self.assert_json_success(result)

    def test_delete(self) -> None:
        emoji_author = self.example_user("iago")
        self.login_user(emoji_author)
        realm_emoji = self.create_test_emoji("my_emoji", emoji_author)
        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_success(result)

        result = self.client_get("/json/realm/emoji")
        emojis = self.assert_json_success(result)["emoji"]
        # We only mark an emoji as deactivated instead of
        # removing it from the database.
        self.assert_length(emojis, 2)
        test_emoji = emojis[str(realm_emoji.id)]
        self.assertEqual(test_emoji["deactivated"], True)

    def test_delete_no_author(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        self.create_test_emoji_with_no_author("my_emoji", realm)
        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_success(result)

    def test_delete_admin_or_author(self) -> None:
        # Admins can delete emoji added by others also.
        # Non-admins can only delete emoji they added themselves.
        emoji_author = self.example_user("othello")

        self.create_test_emoji("my_emoji_1", emoji_author)
        self.login_user(emoji_author)
        result = self.client_delete("/json/realm/emoji/my_emoji_1")
        self.assert_json_success(result)
        self.logout()

        self.create_test_emoji("my_emoji_2", emoji_author)
        self.login("iago")
        result = self.client_delete("/json/realm/emoji/my_emoji_2")
        self.assert_json_success(result)
        self.logout()

        self.create_test_emoji("my_emoji_3", emoji_author)
        self.login("cordelia")
        result = self.client_delete("/json/realm/emoji/my_emoji_3")
        self.assert_json_error(result, "Must be an organization administrator or emoji author")

    def test_delete_exception(self) -> None:
        self.login("iago")
        result = self.client_delete("/json/realm/emoji/invalid_emoji")
        self.assert_json_error(result, "Emoji 'invalid_emoji' does not exist", status_code=404)

    def test_multiple_upload(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1, get_test_image_file("img.png") as fp2:
            result = self.client_post("/json/realm/emoji/my_emoji", {"f1": fp1, "f2": fp2})
        self.assert_json_error(result, "You must upload exactly one file.")

    def test_emoji_upload_success(self) -> None:
        self.login("iago")
        with get_test_image_file("img.gif") as fp:
            result = self.client_post("/json/realm/emoji/my_emoji", {"file": fp})
        self.assert_json_success(result)

    def test_emoji_upload_resize_success(self) -> None:
        self.login("iago")
        with get_test_image_file("still_large_img.gif") as fp:
            result = self.client_post("/json/realm/emoji/my_emoji", {"file": fp})
        self.assert_json_success(result)

    def test_emoji_upload_file_size_error(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp:
            with self.settings(MAX_EMOJI_FILE_SIZE_MIB=0):
                result = self.client_post("/json/realm/emoji/my_emoji", {"file": fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MiB")

    def test_upload_already_existed_emoji(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/green_tick", info=emoji_data)
        self.assert_json_error(result, "A custom emoji with this name already exists.")

    def test_reupload(self) -> None:
        # A user should be able to reupload an emoji with same name.
        self.login("iago")
        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji", info=emoji_data)
        self.assert_json_success(result)

        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_success(result)

        with get_test_image_file("img.png") as fp1:
            emoji_data = {"f1": fp1}
            result = self.client_post("/json/realm/emoji/my_emoji", info=emoji_data)
        self.assert_json_success(result)

        result = self.client_get("/json/realm/emoji")
        emojis = self.assert_json_success(result)["emoji"]
        self.assert_length(emojis, 3)

    def test_failed_file_upload(self) -> None:
        self.login("iago")
        with mock.patch(
            "zerver.lib.upload.local.write_local_file", side_effect=BadImageError(msg="Broken")
        ):
            with get_test_image_file("img.png") as fp1:
                emoji_data = {"f1": fp1}
                result = self.client_post("/json/realm/emoji/my_emoji", info=emoji_data)
        self.assert_json_error(result, "Broken")

    def test_check_admin_realm_emoji(self) -> None:
        # Test that an user A is able to remove a realm emoji uploaded by him
        # and having same name as a deactivated realm emoji uploaded by some
        # other user B.
        emoji_author_1 = self.example_user("cordelia")
        self.create_test_emoji("test_emoji", emoji_author_1)
        self.login_user(emoji_author_1)
        result = self.client_delete("/json/realm/emoji/test_emoji")
        self.assert_json_success(result)

        emoji_author_2 = self.example_user("othello")
        self.create_test_emoji("test_emoji", emoji_author_2)
        self.login_user(emoji_author_2)
        result = self.client_delete("/json/realm/emoji/test_emoji")
        self.assert_json_success(result)

    def test_check_admin_different_realm_emoji(self) -> None:
        # Test that two different realm emojis in two different realms but
        # having same name can be administered independently.
        realm_1 = do_create_realm("test_realm", "test_realm")
        emoji_author_1 = do_create_user(
            "abc@example.com", password="abc", realm=realm_1, full_name="abc", acting_user=None
        )
        self.create_test_emoji("test_emoji", emoji_author_1)

        emoji_author_2 = self.example_user("othello")
        self.create_test_emoji("test_emoji", emoji_author_2)
        self.login_user(emoji_author_2)
        result = self.client_delete("/json/realm/emoji/test_emoji")
        self.assert_json_success(result)

    def test_upload_already_existed_emoji_in_check_add_realm_emoji(self) -> None:
        realm_1 = do_create_realm("test_realm", "test_realm")
        emoji_author = do_create_user(
            "abc@example.com", password="abc", realm=realm_1, full_name="abc", acting_user=None
        )
        emoji_name = "emoji_test"
        with get_test_image_file("img.png") as img_file:
            # Because we want to verify the IntegrityError handling
            # logic in check_add_realm_emoji rather than the primary
            # check in upload_emoji, we need to make this request via
            # that helper rather than via the API.
            check_add_realm_emoji(
                realm=emoji_author.realm, name=emoji_name, author=emoji_author, image_file=img_file
            )
            with self.assertRaises(JsonableError):
                check_add_realm_emoji(
                    realm=emoji_author.realm,
                    name=emoji_name,
                    author=emoji_author,
                    image_file=img_file,
                )
