from typing import Any, TypeAlias

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import encode_stream, get_message_narrow_link
from zerver.models import Message
from zerver.models.recipients import get_direct_message_group_user_ids

NarrowTermFixtureT: TypeAlias = dict[str, dict[str, list[dict[str, Any]]]]


class URLEncodeTest(ZulipTestCase):
    def test_get_gdm_narrow_link_from_message(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        zoe = self.example_user("ZOE")
        gdm_content = "hello iago, zoe"
        group_direct_message_id = self.send_group_direct_message(
            hamlet, [iago, zoe, hamlet], gdm_content
        )
        group_direct_message = Message.objects.get(id=group_direct_message_id)
        gdm_narrow_link = get_message_narrow_link(group_direct_message, "near")
        gdm_recipients = list(get_direct_message_group_user_ids(group_direct_message.recipient))

        encoded_gdm_recipients = ",".join(map(str, gdm_recipients))
        expected_narrow_link = (
            f"#narrow/dm/{encoded_gdm_recipients}-group/near/{group_direct_message_id}"
        )
        self.assertEqual(gdm_narrow_link, expected_narrow_link)

    def test_get_dm_narrow_link_from_message(self) -> None:
        hamlet = self.example_user("hamlet")
        zoe = self.example_user("ZOE")
        dm_content = "hello zoe"
        direct_message_id = self.send_personal_message(hamlet, zoe, dm_content)
        direct_message = Message.objects.get(id=direct_message_id)
        dm_narrow_link = get_message_narrow_link(direct_message, "near")

        encoded_dm_recipient = f"{zoe.id}-{zoe.full_name}"
        expected_narrow_link = f"#narrow/dm/{encoded_dm_recipient}/near/{direct_message_id}"
        self.assertEqual(dm_narrow_link, expected_narrow_link)

    def test_get_channel_narrow_link_from_message(self) -> None:
        hamlet = self.example_user("hamlet")
        public_channel = self.make_stream("public")
        self.subscribe(hamlet, public_channel.name)
        message_content = "hello public"
        channel_message_id = self.send_stream_message(hamlet, public_channel.name, message_content)
        channel_message = Message.objects.get(id=channel_message_id)
        message_narrow_link = get_message_narrow_link(channel_message, "near")

        encoded_channel = encode_stream(public_channel.id, public_channel.name)
        expected_narrow_link = (
            f"#narrow/channel/{encoded_channel}/topic/test/near/{channel_message_id}"
        )
        self.assertEqual(message_narrow_link, expected_narrow_link)

        # Unknown Recipient.type
        channel_message.recipient.type = 4
        with self.assertRaises(AssertionError):
            get_message_narrow_link(channel_message, "near")
