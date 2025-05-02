import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import ChannelFolder
from zerver.models.realms import get_realm


class ChannelFolderCreationTest(ZulipTestCase):
    def test_creating_channel_folder(self) -> None:
        self.login("shiva")
        realm = get_realm("zulip")

        params = {"name": "Frontend", "description": ""}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.filter(realm=realm).last()
        assert channel_folder is not None
        self.assertEqual(channel_folder.name, "Frontend")
        self.assertEqual(channel_folder.description, "")
        response = orjson.loads(result.content)
        self.assertEqual(response["channel_folder_id"], channel_folder.id)

    def test_creating_channel_folder_with_duplicate_name(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")

        params = {"name": "Frontend", "description": ""}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        self.assertTrue(ChannelFolder.objects.filter(realm=realm, name="Frontend").exists())

        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Channel folder 'Frontend' already exists")

    def test_rendered_description_for_channel_folder(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")

        params = {"name": "Frontend", "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(realm=realm, name="Frontend")
        self.assertEqual(channel_folder.description, "Channels for frontend discussions")
        self.assertEqual(
            channel_folder.rendered_description, "<p>Channels for frontend discussions</p>"
        )

        params = {"name": "Backend", "description": "Channels for **backend** discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(realm=realm, name="Backend")
        self.assertEqual(channel_folder.description, "Channels for **backend** discussions")
        self.assertEqual(
            channel_folder.rendered_description,
            "<p>Channels for <strong>backend</strong> discussions</p>",
        )

    def test_invalid_names_for_channel_folder(self) -> None:
        self.login("iago")

        params = {"name": "", "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Channel folder name can't be empty.")

        invalid_name = "abc\000"
        params = {"name": invalid_name, "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Invalid character in channel folder name, at position 4.")
