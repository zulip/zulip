# -*- coding: utf-8 -*-

import mock

from zerver.lib.actions import do_create_realm, do_create_user, \
    get_realm, check_add_realm_emoji
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file
from zerver.models import Realm, RealmEmoji, UserProfile

class RealmEmojiTest(ZulipTestCase):

    def create_test_emoji(self, name: str, author: UserProfile) -> RealmEmoji:
        with get_test_image_file('img.png') as img_file:
            realm_emoji = check_add_realm_emoji(realm=author.realm,
                                                name=name,
                                                author=author,
                                                image_file=img_file)
            if realm_emoji is None:
                raise Exception("Error creating test emoji.")   # nocoverage
        return realm_emoji

    def create_test_emoji_with_no_author(self, name: str, realm: Realm) -> RealmEmoji:
        realm_emoji = RealmEmoji.objects.create(realm=realm, name=name)
        return realm_emoji

    def test_list(self) -> None:
        emoji_author = self.example_user('iago')
        self.login(emoji_author.email)
        self.create_test_emoji('my_emoji', emoji_author)

        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        self.assertEqual(len(result.json()["emoji"]), 2)

    def test_list_no_author(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        realm = get_realm('zulip')
        realm_emoji = self.create_test_emoji_with_no_author('my_emoji', realm)

        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        content = result.json()
        self.assertEqual(len(content["emoji"]), 2)
        test_emoji = content["emoji"][str(realm_emoji.id)]
        self.assertIsNone(test_emoji['author'])

    def test_list_admins_only(self) -> None:
        # Test that realm emoji list is public and realm emojis
        # having no author are also there in the list.
        email = self.example_email('othello')
        self.login(email)
        realm = get_realm('zulip')
        realm.add_emoji_by_admins_only = True
        realm.save()
        realm_emoji = self.create_test_emoji_with_no_author('my_emoji', realm)

        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        content = result.json()
        self.assertEqual(len(content["emoji"]), 2)
        test_emoji = content["emoji"][str(realm_emoji.id)]
        self.assertIsNone(test_emoji['author'])

    def test_upload(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        realm_emoji = RealmEmoji.objects.get(name="my_emoji")
        self.assertEqual(realm_emoji.author.email, email)

        result = self.client_get("/json/realm/emoji")
        content = result.json()
        self.assert_json_success(result)
        self.assertEqual(len(content["emoji"]), 2)
        test_emoji = content["emoji"][str(realm_emoji.id)]
        self.assertIn('author', test_emoji)
        self.assertEqual(test_emoji['author']['email'], email)

    def test_realm_emoji_repr(self) -> None:
        realm_emoji = RealmEmoji.objects.get(name='green_tick')
        file_name = str(realm_emoji.id) + '.png'
        self.assertEqual(
            str(realm_emoji),
            '<RealmEmoji(zulip): %s green_tick False %s>' % (realm_emoji.id, file_name)
        )

    def test_upload_exception(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_em*oji', info=emoji_data)
        self.assert_json_error(result, 'Invalid characters in emoji name')

    def test_upload_uppercase_exception(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_EMoji', info=emoji_data)
        self.assert_json_error(result, 'Invalid characters in emoji name')

    def test_upload_admins_only(self) -> None:
        email = self.example_email('othello')
        self.login(email)
        realm = get_realm('zulip')
        realm.add_emoji_by_admins_only = True
        realm.save()
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_upload_anyone(self) -> None:
        email = self.example_email('othello')
        self.login(email)
        realm = get_realm('zulip')
        realm.add_emoji_by_admins_only = False
        realm.save()
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_success(result)

    def test_emoji_upload_by_guest_user(self) -> None:
        email = self.example_email('polonius')
        self.login(email)
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_error(result, 'Not allowed for guest users')

    def test_delete(self) -> None:
        emoji_author = self.example_user('iago')
        self.login(emoji_author.email)
        realm_emoji = self.create_test_emoji('my_emoji', emoji_author)
        result = self.client_delete('/json/realm/emoji/my_emoji')
        self.assert_json_success(result)

        result = self.client_get("/json/realm/emoji")
        emojis = result.json()["emoji"]
        self.assert_json_success(result)
        # We only mark an emoji as deactivated instead of
        # removing it from the database.
        self.assertEqual(len(emojis), 2)
        test_emoji = emojis[str(realm_emoji.id)]
        self.assertEqual(test_emoji["deactivated"], True)

    def test_delete_no_author(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        realm = get_realm('zulip')
        self.create_test_emoji_with_no_author('my_emoji', realm)
        result = self.client_delete('/json/realm/emoji/my_emoji')
        self.assert_json_success(result)

    def test_delete_admins_only(self) -> None:
        emoji_author = self.example_user('othello')
        self.login(emoji_author.email)
        realm = get_realm('zulip')
        realm.add_emoji_by_admins_only = True
        realm.save()
        self.create_test_emoji_with_no_author("my_emoji", realm)
        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_delete_admin_or_author(self) -> None:
        # If any user in a realm can upload the emoji then the user who
        # uploaded it as well as the admin should be able to delete it.
        emoji_author = self.example_user('othello')
        realm = get_realm('zulip')
        realm.add_emoji_by_admins_only = False
        realm.save()

        self.create_test_emoji('my_emoji_1', emoji_author)
        self.login(emoji_author.email)
        result = self.client_delete("/json/realm/emoji/my_emoji_1")
        self.assert_json_success(result)
        self.logout()

        self.create_test_emoji('my_emoji_2', emoji_author)
        self.login(self.example_email('iago'))
        result = self.client_delete("/json/realm/emoji/my_emoji_2")
        self.assert_json_success(result)
        self.logout()

        self.create_test_emoji('my_emoji_3', emoji_author)
        self.login(self.example_email('cordelia'))
        result = self.client_delete("/json/realm/emoji/my_emoji_3")
        self.assert_json_error(result, 'Must be an organization administrator or emoji author')

    def test_delete_exception(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        result = self.client_delete("/json/realm/emoji/invalid_emoji")
        self.assert_json_error(result, "Emoji 'invalid_emoji' does not exist")

    def test_multiple_upload(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp1, get_test_image_file('img.png') as fp2:
            result = self.client_post('/json/realm/emoji/my_emoji', {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, 'You must upload exactly one file.')

    def test_emoji_upload_file_size_error(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp:
            with self.settings(MAX_EMOJI_FILE_SIZE=0):
                result = self.client_post('/json/realm/emoji/my_emoji', {'file': fp})
        self.assert_json_error(result, 'Uploaded file is larger than the allowed limit of 0 MB')

    def test_upload_already_existed_emoji(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/green_tick', info=emoji_data)
        self.assert_json_error(result, 'A custom emoji with this name already exists.')

    def test_reupload(self) -> None:
        # An user should be able to reupload an emoji with same name.
        email = self.example_email('iago')
        self.login(email)
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_success(result)

        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_success(result)

        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_success(result)

        result = self.client_get("/json/realm/emoji")
        emojis = result.json()["emoji"]
        self.assert_json_success(result)
        self.assertEqual(len(emojis), 3)

    def test_failed_file_upload(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        with mock.patch('zerver.lib.upload.write_local_file', side_effect=Exception()):
            with get_test_image_file('img.png') as fp1:
                emoji_data = {'f1': fp1}
                result = self.client_post('/json/realm/emoji/my_emoji', info=emoji_data)
        self.assert_json_error(result, "Image file upload failed.")

    def test_check_admin_realm_emoji(self) -> None:
        # Test that an user A is able to remove a realm emoji uploaded by him
        # and having same name as a deactivated realm emoji uploaded by some
        # other user B.
        emoji_author_1 = self.example_user('cordelia')
        self.create_test_emoji('test_emoji', emoji_author_1)
        self.login(emoji_author_1.email)
        result = self.client_delete('/json/realm/emoji/test_emoji')
        self.assert_json_success(result)

        emoji_author_2 = self.example_user('othello')
        self.create_test_emoji('test_emoji', emoji_author_2)
        self.login(emoji_author_2.email)
        result = self.client_delete('/json/realm/emoji/test_emoji')
        self.assert_json_success(result)

    def test_check_admin_different_realm_emoji(self) -> None:
        # Test that two different realm emojis in two different realms but
        # having same name can be administered independently.
        realm_1 = do_create_realm('test_realm', 'test_realm')
        emoji_author_1 = do_create_user('abc@example.com',
                                        password='abc',
                                        realm=realm_1,
                                        full_name='abc',
                                        short_name='abc')
        self.create_test_emoji('test_emoji', emoji_author_1)

        emoji_author_2 = self.example_user('othello')
        self.create_test_emoji('test_emoji', emoji_author_2)
        self.login(emoji_author_2.email)
        result = self.client_delete('/json/realm/emoji/test_emoji')
        self.assert_json_success(result)
