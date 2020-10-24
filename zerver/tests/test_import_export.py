import os
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple
from unittest.mock import patch

import orjson
from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now as timezone_now

from zerver.lib import upload
from zerver.lib.actions import (
    do_add_reaction,
    do_change_icon_source,
    do_change_logo_source,
    do_change_plan_type,
    do_create_user,
    do_update_user_presence,
)
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.bot_config import set_bot_config
from zerver.lib.bot_lib import StateHandler
from zerver.lib.export import do_export_realm, do_export_user, export_usermessages_batch
from zerver.lib.import_realm import do_import_realm, get_incoming_message_ids
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import create_s3_buckets, get_test_image_file, use_s3_backend
from zerver.lib.topic_mutes import add_topic_mute
from zerver.lib.upload import (
    claim_attachment,
    upload_avatar_image,
    upload_emoji_image,
    upload_message_file,
)
from zerver.lib.utils import query_chunker
from zerver.models import (
    AlertWord,
    Attachment,
    BotConfigData,
    BotStorageData,
    CustomProfileField,
    CustomProfileFieldValue,
    Huddle,
    Message,
    MutedTopic,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmEmoji,
    Recipient,
    Stream,
    Subscription,
    UserGroup,
    UserGroupMembership,
    UserHotspot,
    UserMessage,
    UserPresence,
    UserProfile,
    get_active_streams,
    get_client,
    get_huddle_hash,
    get_realm,
    get_stream,
)


class QueryUtilTest(ZulipTestCase):
    def _create_messages(self) -> None:
        for name in ['cordelia', 'hamlet', 'iago']:
            user = self.example_user(name)
            for _ in range(5):
                self.send_personal_message(user, self.example_user('othello'))

    def test_query_chunker(self) -> None:
        self._create_messages()

        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')

        def get_queries() -> List[Any]:
            queries = [
                Message.objects.filter(sender_id=cordelia.id),
                Message.objects.filter(sender_id=hamlet.id),
                Message.objects.exclude(sender_id__in=[cordelia.id, hamlet.id]),
            ]
            return queries

        for query in get_queries():
            # For our test to be meaningful, we want non-empty queries
            # at first
            assert len(list(query)) > 0

        queries = get_queries()

        all_msg_ids: Set[int] = set()
        chunker = query_chunker(
            queries=queries,
            id_collector=all_msg_ids,
            chunk_size=20,
        )

        all_row_ids = []
        for chunk in chunker:
            for row in chunk:
                all_row_ids.append(row.id)

        self.assertEqual(all_row_ids, sorted(all_row_ids))
        self.assertEqual(len(all_msg_ids), len(Message.objects.all()))

        # Now just search for cordelia/hamlet.  Note that we don't really
        # need the order_by here, but it should be harmless.
        queries = [
            Message.objects.filter(sender_id=cordelia.id).order_by('id'),
            Message.objects.filter(sender_id=hamlet.id),
        ]
        all_msg_ids = set()
        chunker = query_chunker(
            queries=queries,
            id_collector=all_msg_ids,
            chunk_size=7,  # use a different size
        )
        list(chunker)  # exhaust the iterator
        self.assertEqual(
            len(all_msg_ids),
            len(Message.objects.filter(sender_id__in=[cordelia.id, hamlet.id])),
        )

        # Try just a single query to validate chunking.
        queries = [
            Message.objects.exclude(sender_id=cordelia.id),
        ]
        all_msg_ids = set()
        chunker = query_chunker(
            queries=queries,
            id_collector=all_msg_ids,
            chunk_size=11,  # use a different size each time
        )
        list(chunker)  # exhaust the iterator
        self.assertEqual(
            len(all_msg_ids),
            len(Message.objects.exclude(sender_id=cordelia.id)),
        )
        self.assertTrue(len(all_msg_ids) > 15)

        # Verify assertions about disjoint-ness.
        queries = [
            Message.objects.exclude(sender_id=cordelia.id),
            Message.objects.filter(sender_id=hamlet.id),
        ]
        all_msg_ids = set()
        chunker = query_chunker(
            queries=queries,
            id_collector=all_msg_ids,
            chunk_size=13,  # use a different size each time
        )
        with self.assertRaises(AssertionError):
            list(chunker)  # exercise the iterator

        # Try to confuse things with ids part of the query...
        queries = [
            Message.objects.filter(id__lte=10),
            Message.objects.filter(id__gt=10),
        ]
        all_msg_ids = set()
        chunker = query_chunker(
            queries=queries,
            id_collector=all_msg_ids,
            chunk_size=11,  # use a different size each time
        )
        self.assertEqual(len(all_msg_ids), 0)  # until we actually use the iterator
        list(chunker)  # exhaust the iterator
        self.assertEqual(len(all_msg_ids), len(Message.objects.all()))

        # Verify that we can just get the first chunk with a next() call.
        queries = [
            Message.objects.all(),
        ]
        all_msg_ids = set()
        chunker = query_chunker(
            queries=queries,
            id_collector=all_msg_ids,
            chunk_size=10,  # use a different size each time
        )
        first_chunk = next(chunker)
        self.assertEqual(len(first_chunk), 10)
        self.assertEqual(len(all_msg_ids), 10)
        expected_msg = Message.objects.all()[0:10][5]
        actual_msg = first_chunk[5]
        self.assertEqual(actual_msg.content, expected_msg.content)
        self.assertEqual(actual_msg.sender_id, expected_msg.sender_id)


class ImportExportTest(ZulipTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.rm_tree(settings.LOCAL_UPLOADS_DIR)

    def _make_output_dir(self) -> str:
        output_dir = os.path.join(settings.TEST_WORKER_DIR, 'test-export')
        self.rm_tree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _export_realm(self, realm: Realm, exportable_user_ids: Optional[Set[int]]=None,
                      consent_message_id: Optional[int]=None) -> Dict[str, Any]:
        output_dir = self._make_output_dir()
        with patch('logging.info'), patch('zerver.lib.export.create_soft_link'):
            do_export_realm(
                realm=realm,
                output_dir=output_dir,
                threads=0,
                exportable_user_ids=exportable_user_ids,
                consent_message_id=consent_message_id,
            )
            export_usermessages_batch(
                input_path=os.path.join(output_dir, 'messages-000001.json.partial'),
                output_path=os.path.join(output_dir, 'messages-000001.json'),
                consent_message_id=consent_message_id,
            )

            try:
                export_usermessages_batch(
                    input_path=os.path.join(output_dir, 'messages-000002.json.partial'),
                    output_path=os.path.join(output_dir, 'messages-000002.json'),
                    consent_message_id=consent_message_id,
                )
            except FileNotFoundError:
                pass

        def read_file(fn: str) -> Any:
            full_fn = os.path.join(output_dir, fn)
            with open(full_fn, "rb") as f:
                return orjson.loads(f.read())

        result = {}
        result['realm'] = read_file('realm.json')
        result['attachment'] = read_file('attachment.json')
        result['message'] = read_file('messages-000001.json')
        try:
            message = read_file('messages-000002.json')
            result["message"]["zerver_usermessage"].extend(message["zerver_usermessage"])
            result["message"]["zerver_message"].extend(message["zerver_message"])
        except FileNotFoundError:
            pass
        result['uploads_dir'] = os.path.join(output_dir, 'uploads')
        result['uploads_dir_records'] = read_file(os.path.join('uploads', 'records.json'))
        result['emoji_dir'] = os.path.join(output_dir, 'emoji')
        result['emoji_dir_records'] = read_file(os.path.join('emoji', 'records.json'))
        result['avatar_dir'] = os.path.join(output_dir, 'avatars')
        result['avatar_dir_records'] = read_file(os.path.join('avatars', 'records.json'))
        result['realm_icons_dir'] = os.path.join(output_dir, 'realm_icons')
        result['realm_icons_dir_records'] = read_file(os.path.join('realm_icons', 'records.json'))
        return result

    def _setup_export_files(self, realm: Realm) -> Tuple[str, str, str, bytes]:
        message = Message.objects.all()[0]
        user_profile = message.sender
        url = upload_message_file('dummy.txt', len(b'zulip!'), 'text/plain', b'zulip!', user_profile)
        attachment_path_id = url.replace('/user_uploads/', '')
        claim_attachment(
            user_profile=user_profile,
            path_id=attachment_path_id,
            message=message,
            is_message_realm_public=True,
        )
        avatar_path_id = user_avatar_path(user_profile)
        original_avatar_path_id = avatar_path_id + ".original"

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=realm.id,
            emoji_file_name='1.png',
        )

        with get_test_image_file('img.png') as img_file:
            upload_emoji_image(img_file, '1.png', user_profile)
        with get_test_image_file('img.png') as img_file:
            upload_avatar_image(img_file, user_profile, user_profile)

        with get_test_image_file('img.png') as img_file:
            upload.upload_backend.upload_realm_icon_image(img_file, user_profile)
            do_change_icon_source(realm, Realm.ICON_UPLOADED)

        with get_test_image_file('img.png') as img_file:
            upload.upload_backend.upload_realm_logo_image(img_file, user_profile, night=False)
            do_change_logo_source(realm, Realm.LOGO_UPLOADED, False, acting_user=user_profile)
        with get_test_image_file('img.png') as img_file:
            upload.upload_backend.upload_realm_logo_image(img_file, user_profile, night=True)
            do_change_logo_source(realm, Realm.LOGO_UPLOADED, True, acting_user=user_profile)

        with get_test_image_file('img.png') as img_file:
            test_image = img_file.read()
        message.sender.avatar_source = 'U'
        message.sender.save()

        realm.refresh_from_db()

        return attachment_path_id, emoji_path, original_avatar_path_id, test_image

    """
    Tests for export
    """

    def test_export_files_from_local(self) -> None:
        realm = Realm.objects.get(string_id='zulip')
        path_id, emoji_path, original_avatar_path_id, test_image = self._setup_export_files(realm)
        full_data = self._export_realm(realm)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], path_id)

        # Test uploads
        fn = os.path.join(full_data['uploads_dir'], path_id)
        with open(fn) as f:
            self.assertEqual(f.read(), 'zulip!')
        records = full_data['uploads_dir_records']
        self.assertEqual(records[0]['path'], path_id)
        self.assertEqual(records[0]['s3_path'], path_id)

        # Test emojis
        fn = os.path.join(full_data['emoji_dir'], emoji_path)
        fn = fn.replace('1.png', '')
        self.assertEqual('1.png', os.listdir(fn)[0])
        records = full_data['emoji_dir_records']
        self.assertEqual(records[0]['file_name'], '1.png')
        self.assertEqual(records[0]['path'], '2/emoji/images/1.png')
        self.assertEqual(records[0]['s3_path'], '2/emoji/images/1.png')

        # Test realm logo and icon
        records = full_data['realm_icons_dir_records']
        image_files = set()
        for record in records:
            image_path = os.path.join(full_data['realm_icons_dir'], record["path"])
            if image_path[-9:] == ".original":
                with open(image_path, 'rb') as image_file:
                    image_data = image_file.read()
                self.assertEqual(image_data, test_image)
            else:
                self.assertTrue(os.path.exists(image_path))

            image_files.add(os.path.basename(image_path))
        self.assertEqual(set(image_files), {'night_logo.png', 'logo.original', 'logo.png',
                                            'icon.png', 'night_logo.original', 'icon.original'})

        # Test avatars
        fn = os.path.join(full_data['avatar_dir'], original_avatar_path_id)
        with open(fn, 'rb') as fb:
            fn_data = fb.read()
        self.assertEqual(fn_data, test_image)
        records = full_data['avatar_dir_records']
        record_path = [record['path'] for record in records]
        record_s3_path = [record['s3_path'] for record in records]
        self.assertIn(original_avatar_path_id, record_path)
        self.assertIn(original_avatar_path_id, record_s3_path)

    @use_s3_backend
    def test_export_files_from_s3(self) -> None:
        create_s3_buckets(
            settings.S3_AUTH_UPLOADS_BUCKET,
            settings.S3_AVATAR_BUCKET)

        realm = Realm.objects.get(string_id='zulip')
        attachment_path_id, emoji_path, original_avatar_path_id, test_image = self._setup_export_files(realm)
        full_data = self._export_realm(realm)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], attachment_path_id)

        def check_types(user_profile_id: int, realm_id: int) -> None:
            self.assertEqual(type(user_profile_id), int)
            self.assertEqual(type(realm_id), int)

        # Test uploads
        fields = attachment_path_id.split('/')
        fn = os.path.join(full_data['uploads_dir'], os.path.join(fields[0], fields[1], fields[2]))
        with open(fn) as f:
            self.assertEqual(f.read(), 'zulip!')
        records = full_data['uploads_dir_records']
        self.assertEqual(records[0]['path'], os.path.join(fields[0], fields[1], fields[2]))
        self.assertEqual(records[0]['s3_path'], attachment_path_id)
        check_types(records[0]['user_profile_id'], records[0]['realm_id'])

        # Test emojis
        fn = os.path.join(full_data['emoji_dir'], emoji_path)
        fn = fn.replace('1.png', '')
        self.assertIn('1.png', os.listdir(fn))
        records = full_data['emoji_dir_records']
        self.assertEqual(records[0]['file_name'], '1.png')
        self.assertTrue('last_modified' in records[0])
        self.assertEqual(records[0]['path'], '2/emoji/images/1.png')
        self.assertEqual(records[0]['s3_path'], '2/emoji/images/1.png')
        check_types(records[0]['user_profile_id'], records[0]['realm_id'])

        # Test realm logo and icon
        records = full_data['realm_icons_dir_records']
        image_files = set()
        for record in records:
            image_path = os.path.join(full_data['realm_icons_dir'], record["s3_path"])
            if image_path[-9:] == ".original":
                with open(image_path, 'rb') as image_file:
                    image_data = image_file.read()
                self.assertEqual(image_data, test_image)
            else:
                self.assertTrue(os.path.exists(image_path))

            image_files.add(os.path.basename(image_path))
        self.assertEqual(set(image_files), {'night_logo.png', 'logo.original', 'logo.png',
                                            'icon.png', 'night_logo.original', 'icon.original'})

        # Test avatars
        fn = os.path.join(full_data['avatar_dir'], original_avatar_path_id)
        with open(fn, 'rb') as file:
            fn_data = file.read()
        self.assertEqual(fn_data, test_image)
        records = full_data['avatar_dir_records']
        record_path = [record['path'] for record in records]
        record_s3_path = [record['s3_path'] for record in records]
        self.assertIn(original_avatar_path_id, record_path)
        self.assertIn(original_avatar_path_id, record_s3_path)
        check_types(records[0]['user_profile_id'], records[0]['realm_id'])

    def test_zulip_realm(self) -> None:
        realm = Realm.objects.get(string_id='zulip')

        default_bot = self.example_user('default_bot')
        pm_a_msg_id = self.send_personal_message(self.example_user("AARON"), default_bot)
        pm_b_msg_id = self.send_personal_message(default_bot, self.example_user("iago"))
        pm_c_msg_id = self.send_personal_message(self.example_user("othello"), self.example_user("hamlet"))

        realm_emoji = RealmEmoji.objects.get(realm=realm)
        realm_emoji.delete()
        full_data = self._export_realm(realm)
        realm_emoji.save()

        data = full_data['realm']
        self.assertEqual(len(data['zerver_userprofile_crossrealm']), 3)
        self.assertEqual(len(data['zerver_userprofile_mirrordummy']), 0)

        exported_user_emails = self.get_set(data['zerver_userprofile'], 'delivery_email')
        self.assertIn(self.example_email('cordelia'), exported_user_emails)
        self.assertIn('default-bot@zulip.com', exported_user_emails)

        exported_streams = self.get_set(data['zerver_stream'], 'name')
        self.assertEqual(
            exported_streams,
            {'Denmark', 'Rome', 'Scotland', 'Venice', 'Verona'},
        )

        exported_alert_words = data['zerver_alertword']

        # We set up 4 alert words for Hamlet, Cordelia, etc.
        # when we populate the test database.
        num_zulip_users = 9
        self.assertEqual(len(exported_alert_words), num_zulip_users * 4)

        self.assertIn(
            'robotics',
            {r['word'] for r in exported_alert_words}
        )

        data = full_data['message']
        um = UserMessage.objects.all()[0]
        exported_um = self.find_by_id(data['zerver_usermessage'], um.id)
        self.assertEqual(exported_um['message'], um.message_id)
        self.assertEqual(exported_um['user_profile'], um.user_profile_id)

        exported_message = self.find_by_id(data['zerver_message'], um.message_id)
        self.assertEqual(exported_message['content'], um.message.content)

        exported_message_ids = self.get_set(data['zerver_message'], "id")
        self.assertIn(pm_a_msg_id, exported_message_ids)
        self.assertIn(pm_b_msg_id, exported_message_ids)
        self.assertIn(pm_c_msg_id, exported_message_ids)

    def test_export_realm_with_exportable_user_ids(self) -> None:
        realm = Realm.objects.get(string_id='zulip')

        cordelia = self.example_user('iago')
        hamlet = self.example_user('hamlet')
        user_ids = {cordelia.id, hamlet.id}

        pm_a_msg_id = self.send_personal_message(self.example_user("AARON"), self.example_user("othello"))
        pm_b_msg_id = self.send_personal_message(self.example_user("cordelia"), self.example_user("iago"))
        pm_c_msg_id = self.send_personal_message(self.example_user("hamlet"), self.example_user("othello"))
        pm_d_msg_id = self.send_personal_message(self.example_user("iago"), self.example_user("hamlet"))

        realm_emoji = RealmEmoji.objects.get(realm=realm)
        realm_emoji.delete()
        full_data = self._export_realm(realm, exportable_user_ids=user_ids)
        realm_emoji.save()

        data = full_data['realm']

        exported_user_emails = self.get_set(data['zerver_userprofile'], 'delivery_email')
        self.assertIn(self.example_email('iago'), exported_user_emails)
        self.assertIn(self.example_email('hamlet'), exported_user_emails)
        self.assertNotIn('default-bot@zulip.com', exported_user_emails)
        self.assertNotIn(self.example_email('cordelia'), exported_user_emails)

        dummy_user_emails = self.get_set(data['zerver_userprofile_mirrordummy'], 'delivery_email')
        self.assertIn(self.example_email('cordelia'), dummy_user_emails)
        self.assertIn(self.example_email('othello'), dummy_user_emails)
        self.assertIn('default-bot@zulip.com', dummy_user_emails)
        self.assertNotIn(self.example_email('iago'), dummy_user_emails)
        self.assertNotIn(self.example_email('hamlet'), dummy_user_emails)

        data = full_data['message']

        exported_message_ids = self.get_set(data['zerver_message'], "id")
        self.assertNotIn(pm_a_msg_id, exported_message_ids)
        self.assertIn(pm_b_msg_id, exported_message_ids)
        self.assertIn(pm_c_msg_id, exported_message_ids)
        self.assertIn(pm_d_msg_id, exported_message_ids)

    def test_export_realm_with_member_consent(self) -> None:
        realm = Realm.objects.get(string_id='zulip')

        # Create private streams and subscribe users for testing export
        create_stream_if_needed(realm, "Private A", invite_only=True)
        self.subscribe(self.example_user("iago"), "Private A")
        self.subscribe(self.example_user("othello"), "Private A")
        self.send_stream_message(self.example_user("iago"), "Private A", "Hello Stream A")

        create_stream_if_needed(realm, "Private B", invite_only=True)
        self.subscribe(self.example_user("prospero"), "Private B")
        stream_b_message_id = self.send_stream_message(self.example_user("prospero"),
                                                       "Private B", "Hello Stream B")
        self.subscribe(self.example_user("hamlet"), "Private B")

        create_stream_if_needed(realm, "Private C", invite_only=True)
        self.subscribe(self.example_user("othello"), "Private C")
        self.subscribe(self.example_user("prospero"), "Private C")
        stream_c_message_id = self.send_stream_message(self.example_user("othello"),
                                                       "Private C", "Hello Stream C")

        # Create huddles
        self.send_huddle_message(self.example_user("iago"), [self.example_user("cordelia"),
                                                             self.example_user("AARON")])
        huddle_a = Huddle.objects.last()
        self.send_huddle_message(self.example_user("ZOE"), [self.example_user("hamlet"),
                                                            self.example_user("AARON"),
                                                            self.example_user("othello")])
        huddle_b = Huddle.objects.last()

        huddle_c_message_id = self.send_huddle_message(
            self.example_user("AARON"), [self.example_user("cordelia"),
                                         self.example_user("ZOE"),
                                         self.example_user("othello")])

        # Create PMs
        pm_a_msg_id = self.send_personal_message(self.example_user("AARON"), self.example_user("othello"))
        pm_b_msg_id = self.send_personal_message(self.example_user("cordelia"), self.example_user("iago"))
        pm_c_msg_id = self.send_personal_message(self.example_user("hamlet"), self.example_user("othello"))
        pm_d_msg_id = self.send_personal_message(self.example_user("iago"), self.example_user("hamlet"))

        # Send message advertising export and make users react
        self.send_stream_message(self.example_user("othello"), "Verona",
                                 topic_name="Export",
                                 content="Thumbs up for export")
        message = Message.objects.last()
        consented_user_ids = [self.example_user(user).id for user in ["iago", "hamlet"]]
        do_add_reaction(self.example_user("iago"), message, "outbox", "1f4e4",  Reaction.UNICODE_EMOJI)
        do_add_reaction(self.example_user("hamlet"), message, "outbox", "1f4e4",  Reaction.UNICODE_EMOJI)

        realm_emoji = RealmEmoji.objects.get(realm=realm)
        realm_emoji.delete()
        full_data = self._export_realm(realm, consent_message_id=message.id)
        realm_emoji.save()

        data = full_data['realm']

        self.assertEqual(len(data['zerver_userprofile_crossrealm']), 3)
        self.assertEqual(len(data['zerver_userprofile_mirrordummy']), 0)

        exported_user_emails = self.get_set(data['zerver_userprofile'], 'delivery_email')
        self.assertIn(self.example_email('cordelia'), exported_user_emails)
        self.assertIn(self.example_email('hamlet'), exported_user_emails)
        self.assertIn(self.example_email('iago'), exported_user_emails)
        self.assertIn(self.example_email('othello'), exported_user_emails)
        self.assertIn('default-bot@zulip.com', exported_user_emails)

        exported_streams = self.get_set(data['zerver_stream'], 'name')
        self.assertEqual(
            exported_streams,
            {'Denmark', 'Rome', 'Scotland', 'Venice', 'Verona',
             'Private A', 'Private B', 'Private C'},
        )

        data = full_data['message']
        exported_usermessages = UserMessage.objects.filter(user_profile__in=[self.example_user("iago"),
                                                                             self.example_user("hamlet")])
        um = exported_usermessages[0]
        self.assertEqual(len(data["zerver_usermessage"]), len(exported_usermessages))
        exported_um = self.find_by_id(data['zerver_usermessage'], um.id)
        self.assertEqual(exported_um['message'], um.message_id)
        self.assertEqual(exported_um['user_profile'], um.user_profile_id)

        exported_message = self.find_by_id(data['zerver_message'], um.message_id)
        self.assertEqual(exported_message['content'], um.message.content)

        public_stream_names = ['Denmark', 'Rome', 'Scotland', 'Venice', 'Verona']
        public_stream_ids = Stream.objects.filter(name__in=public_stream_names).values_list("id", flat=True)
        public_stream_recipients = Recipient.objects.filter(type_id__in=public_stream_ids, type=Recipient.STREAM)
        public_stream_message_ids = Message.objects.filter(recipient__in=public_stream_recipients).values_list("id", flat=True)

        # Messages from Private Stream C are not exported since no member gave consent
        private_stream_ids = Stream.objects.filter(name__in=["Private A", "Private B"]).values_list("id", flat=True)
        private_stream_recipients = Recipient.objects.filter(type_id__in=private_stream_ids, type=Recipient.STREAM)
        private_stream_message_ids = Message.objects.filter(recipient__in=private_stream_recipients).values_list("id", flat=True)

        pm_recipients = Recipient.objects.filter(type_id__in=consented_user_ids, type=Recipient.PERSONAL)
        pm_query = Q(recipient__in=pm_recipients) | Q(sender__in=consented_user_ids)
        exported_pm_ids = Message.objects.filter(pm_query).values_list("id", flat=True).values_list("id", flat=True)

        # Third huddle is not exported since none of the members gave consent
        huddle_recipients = Recipient.objects.filter(type_id__in=[huddle_a.id, huddle_b.id], type=Recipient.HUDDLE)
        pm_query = Q(recipient__in=huddle_recipients) | Q(sender__in=consented_user_ids)
        exported_huddle_ids = Message.objects.filter(pm_query).values_list("id", flat=True).values_list("id", flat=True)

        exported_msg_ids = set(public_stream_message_ids) | set(private_stream_message_ids) \
            | set(exported_pm_ids) | set(exported_huddle_ids)
        self.assertEqual(self.get_set(data["zerver_message"], "id"), exported_msg_ids)

        # TODO: This behavior is wrong and should be fixed. The message should not be exported
        # since it was sent before the only consented user iago joined the stream.
        self.assertIn(stream_b_message_id, exported_msg_ids)

        self.assertNotIn(stream_c_message_id, exported_msg_ids)
        self.assertNotIn(huddle_c_message_id, exported_msg_ids)

        self.assertNotIn(pm_a_msg_id, exported_msg_ids)
        self.assertIn(pm_b_msg_id, exported_msg_ids)
        self.assertIn(pm_c_msg_id, exported_msg_ids)
        self.assertIn(pm_d_msg_id, exported_msg_ids)

    def test_export_single_user(self) -> None:
        output_dir = self._make_output_dir()
        cordelia = self.example_user('cordelia')

        with patch('logging.info'):
            do_export_user(cordelia, output_dir)

        def read_file(fn: str) -> Any:
            full_fn = os.path.join(output_dir, fn)
            with open(full_fn, "rb") as f:
                return orjson.loads(f.read())

        messages = read_file('messages-000001.json')
        user = read_file('user.json')

        exported_user_id = self.get_set(user['zerver_userprofile'], 'id')
        self.assertEqual(exported_user_id, {cordelia.id})
        exported_user_email = self.get_set(user['zerver_userprofile'], 'email')
        self.assertEqual(exported_user_email, {cordelia.email})

        exported_recipient_type_id = self.get_set(user['zerver_recipient'], 'type_id')
        self.assertIn(cordelia.id, exported_recipient_type_id)

        exported_stream_id = self.get_set(user['zerver_stream'], 'id')
        self.assertIn(list(exported_stream_id)[0], exported_recipient_type_id)

        exported_recipient_id = self.get_set(user['zerver_recipient'], 'id')
        exported_subscription_recipient = self.get_set(user['zerver_subscription'], 'recipient')
        self.assertEqual(exported_recipient_id, exported_subscription_recipient)

        exported_messages_recipient = self.get_set(messages['zerver_message'], 'recipient')
        self.assertIn(list(exported_messages_recipient)[0], exported_recipient_id)

    """
    Tests for import_realm
    """

    def test_import_realm(self) -> None:

        original_realm = Realm.objects.get(string_id='zulip')
        RealmEmoji.objects.get(realm=original_realm).delete()
        # data to test import of huddles
        huddle = [
            self.example_user('hamlet'),
            self.example_user('othello'),
        ]
        self.send_huddle_message(
            self.example_user('cordelia'), huddle, 'test huddle message',
        )

        user_mention_message = '@**King Hamlet** Hello'
        self.send_stream_message(self.example_user("iago"), "Verona", user_mention_message)

        stream_mention_message = 'Subscribe to #**Denmark**'
        self.send_stream_message(self.example_user("hamlet"), "Verona", stream_mention_message)

        user_group_mention_message = 'Hello @*hamletcharacters*'
        self.send_stream_message(self.example_user("othello"), "Verona", user_group_mention_message)

        special_characters_message = "```\n'\n```\n@**Polonius**"
        self.send_stream_message(self.example_user("iago"), "Denmark", special_characters_message)

        sample_user = self.example_user('hamlet')

        # data to test import of hotspots
        UserHotspot.objects.create(
            user=sample_user, hotspot='intro_streams',
        )

        # data to test import of muted topic
        stream = get_stream('Verona', original_realm)
        add_topic_mute(
            user_profile=sample_user,
            stream_id=stream.id,
            recipient_id=stream.recipient.id,
            topic_name='Verona2')

        do_update_user_presence(sample_user, get_client("website"), timezone_now(), UserPresence.ACTIVE)

        # data to test import of botstoragedata and botconfigdata
        bot_profile = do_create_user(
            email="bot-1@zulip.com",
            password="test",
            realm=original_realm,
            full_name="bot",
            bot_type=UserProfile.EMBEDDED_BOT,
            bot_owner=sample_user)
        storage = StateHandler(bot_profile)
        storage.put('some key', 'some value')

        set_bot_config(bot_profile, 'entry 1', 'value 1')

        self._export_realm(original_realm)

        with patch('logging.info'):
            with self.settings(BILLING_ENABLED=False):
                do_import_realm(os.path.join(settings.TEST_WORKER_DIR, 'test-export'),
                                'test-zulip')

        # sanity checks

        # test realm
        self.assertTrue(Realm.objects.filter(string_id='test-zulip').exists())
        imported_realm = Realm.objects.get(string_id='test-zulip')
        self.assertNotEqual(imported_realm.id, original_realm.id)

        def assert_realm_values(f: Callable[[Realm], Any], equal: bool=True) -> None:
            orig_realm_result = f(original_realm)
            imported_realm_result = f(imported_realm)
            # orig_realm_result should be truthy and have some values, otherwise
            # the test is kind of meaningless
            assert(orig_realm_result)
            if equal:
                self.assertEqual(orig_realm_result, imported_realm_result)
            else:
                self.assertNotEqual(orig_realm_result, imported_realm_result)

        # test users
        assert_realm_values(
            lambda r: {user.email for user in r.get_admin_users_and_bots()},
        )

        assert_realm_values(
            lambda r: {user.email for user in r.get_active_users()},
        )

        # test stream
        assert_realm_values(
            lambda r: {stream.name for stream in get_active_streams(r)},
        )

        # test recipients
        def get_recipient_stream(r: Realm) -> Recipient:
            return Stream.objects.get(name='Verona', realm=r).recipient

        def get_recipient_user(r: Realm) -> Recipient:
            return UserProfile.objects.get(full_name='Iago', realm=r).recipient

        assert_realm_values(lambda r: get_recipient_stream(r).type)
        assert_realm_values(lambda r: get_recipient_user(r).type)

        # test subscription
        def get_subscribers(recipient: Recipient) -> Set[str]:
            subscriptions = Subscription.objects.filter(recipient=recipient)
            users = {sub.user_profile.email for sub in subscriptions}
            return users

        assert_realm_values(
            lambda r: get_subscribers(get_recipient_stream(r)),
        )

        assert_realm_values(
            lambda r: get_subscribers(get_recipient_user(r)),
        )

        # test custom profile fields
        def get_custom_profile_field_names(r: Realm) -> Set[str]:
            custom_profile_fields = CustomProfileField.objects.filter(realm=r)
            custom_profile_field_names = {field.name for field in custom_profile_fields}
            return custom_profile_field_names

        assert_realm_values(get_custom_profile_field_names)

        def get_custom_profile_with_field_type_user(r: Realm) -> Tuple[Set[Any],
                                                                       Set[Any],
                                                                       Set[FrozenSet[str]]]:
            fields = CustomProfileField.objects.filter(
                field_type=CustomProfileField.USER,
                realm=r)

            def get_email(user_id: int) -> str:
                return UserProfile.objects.get(id=user_id).email

            def get_email_from_value(field_value: CustomProfileFieldValue) -> Set[str]:
                user_id_list = orjson.loads(field_value.value)
                return {get_email(user_id) for user_id in user_id_list}

            def custom_profile_field_values_for(fields: List[CustomProfileField]) -> Set[FrozenSet[str]]:
                user_emails: Set[FrozenSet[str]] = set()
                for field in fields:
                    values = CustomProfileFieldValue.objects.filter(field=field)
                    for value in values:
                        user_emails.add(frozenset(get_email_from_value(value)))
                return user_emails

            field_names, field_hints = (set() for i in range(2))
            for field in fields:
                field_names.add(field.name)
                field_hints.add(field.hint)

            return (field_hints, field_names, custom_profile_field_values_for(fields))

        assert_realm_values(get_custom_profile_with_field_type_user)

        # test realmauditlog
        def get_realm_audit_log_event_type(r: Realm) -> Set[str]:
            realmauditlogs = RealmAuditLog.objects.filter(realm=r).exclude(
                event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
            realmauditlog_event_type = {log.event_type for log in realmauditlogs}
            return realmauditlog_event_type

        assert_realm_values(get_realm_audit_log_event_type)

        cordelia_full_name = 'Cordelia Lear'
        hamlet_full_name = 'King Hamlet'
        othello_full_name = 'Othello, the Moor of Venice'

        def get_user_id(r: Realm, full_name: str) -> int:
            return UserProfile.objects.get(realm=r, full_name=full_name).id

        # test huddles
        def get_huddle_hashes(r: Realm) -> str:
            user_id_list = [
                get_user_id(r, cordelia_full_name),
                get_user_id(r, hamlet_full_name),
                get_user_id(r, othello_full_name),
            ]

            huddle_hash = get_huddle_hash(user_id_list)
            return huddle_hash

        assert_realm_values(get_huddle_hashes, equal=False)

        def get_huddle_message(r: Realm) -> str:
            huddle_hash = get_huddle_hashes(r)
            huddle_id = Huddle.objects.get(huddle_hash=huddle_hash).id
            huddle_recipient = Recipient.objects.get(type_id=huddle_id, type=3)
            huddle_message = Message.objects.get(recipient=huddle_recipient)
            return huddle_message.content

        assert_realm_values(get_huddle_message)
        self.assertEqual(get_huddle_message(imported_realm), 'test huddle message')

        # test alertword
        def get_alertwords(r: Realm) -> Set[str]:
            return {
                rec.word
                for rec in
                AlertWord.objects.filter(realm_id=r.id)
            }

        assert_realm_values(get_alertwords)

        # test userhotspot
        def get_user_hotspots(r: Realm) -> Set[str]:
            user_id = get_user_id(r, hamlet_full_name)
            hotspots = UserHotspot.objects.filter(user_id=user_id)
            user_hotspots = {hotspot.hotspot for hotspot in hotspots}
            return user_hotspots

        assert_realm_values(get_user_hotspots)

        # test muted topics
        def get_muted_topics(r: Realm) -> Set[str]:
            user_profile_id = get_user_id(r, hamlet_full_name)
            muted_topics = MutedTopic.objects.filter(user_profile_id=user_profile_id)
            topic_names = {muted_topic.topic_name for muted_topic in muted_topics}
            return topic_names

        assert_realm_values(get_muted_topics)

        # test usergroups
        assert_realm_values(
            lambda r: {group.name for group in UserGroup.objects.filter(realm=r)},
        )

        def get_user_membership(r: Realm) -> Set[str]:
            usergroup = UserGroup.objects.get(realm=r, name='hamletcharacters')
            usergroup_membership = UserGroupMembership.objects.filter(user_group=usergroup)
            users = {membership.user_profile.email for membership in usergroup_membership}
            return users

        assert_realm_values(get_user_membership)

        # test botstoragedata and botconfigdata
        def get_botstoragedata(r: Realm) -> Dict[str, Any]:
            bot_profile = UserProfile.objects.get(full_name="bot", realm=r)
            bot_storage_data = BotStorageData.objects.get(bot_profile=bot_profile)
            return {'key': bot_storage_data.key, 'data': bot_storage_data.value}

        assert_realm_values(get_botstoragedata)

        def get_botconfigdata(r: Realm) -> Dict[str, Any]:
            bot_profile = UserProfile.objects.get(full_name="bot", realm=r)
            bot_config_data = BotConfigData.objects.get(bot_profile=bot_profile)
            return {'key': bot_config_data.key, 'data': bot_config_data.value}

        assert_realm_values(get_botconfigdata)

        # test messages
        def get_stream_messages(r: Realm) -> Message:
            recipient = get_recipient_stream(r)
            messages = Message.objects.filter(recipient=recipient)
            return messages

        def get_stream_topics(r: Realm) -> Set[str]:
            messages = get_stream_messages(r)
            topics = {m.topic_name() for m in messages}
            return topics

        assert_realm_values(get_stream_topics)

        # test usermessages
        def get_usermessages_user(r: Realm) -> Set[Any]:
            messages = get_stream_messages(r).order_by('content')
            usermessage = UserMessage.objects.filter(message=messages[0])
            usermessage_user = {um.user_profile.email for um in usermessage}
            return usermessage_user

        assert_realm_values(get_usermessages_user)

        # tests to make sure that various data-*-ids in rendered_content
        # are replaced correctly with the values of newer realm.

        def get_user_mention(r: Realm) -> Set[Any]:
            mentioned_user = UserProfile.objects.get(delivery_email=self.example_email("hamlet"), realm=r)
            data_user_id = f'data-user-id="{mentioned_user.id}"'
            mention_message = get_stream_messages(r).get(rendered_content__contains=data_user_id)
            return mention_message.content

        assert_realm_values(get_user_mention)

        def get_stream_mention(r: Realm) -> Set[Any]:
            mentioned_stream = get_stream('Denmark', r)
            data_stream_id = f'data-stream-id="{mentioned_stream.id}"'
            mention_message = get_stream_messages(r).get(rendered_content__contains=data_stream_id)
            return mention_message.content

        assert_realm_values(get_stream_mention)

        def get_user_group_mention(r: Realm) -> Set[Any]:
            user_group = UserGroup.objects.get(realm=r, name='hamletcharacters')
            data_usergroup_id = f'data-user-group-id="{user_group.id}"'
            mention_message = get_stream_messages(r).get(rendered_content__contains=data_usergroup_id)
            return mention_message.content

        assert_realm_values(get_user_group_mention)

        def get_userpresence_timestamp(r: Realm) -> Set[Any]:
            # It should be sufficient to compare UserPresence timestamps to verify
            # they got exported/imported correctly.
            return set(UserPresence.objects.filter(realm=r).values_list('timestamp', flat=True))

        assert_realm_values(get_userpresence_timestamp)

        # test to highlight that bs4 which we use to do data-**id
        # replacements modifies the HTML sometimes. eg replacing <br>
        # with </br>, &#39; with \' etc. The modifications doesn't
        # affect how the browser displays the rendered_content so we
        # are okay with using bs4 for this.  lxml package also has
        # similar behavior.
        orig_polonius_user = self.example_user('polonius')
        original_msg = Message.objects.get(content=special_characters_message, sender__realm=original_realm)
        self.assertEqual(
            original_msg.rendered_content,
            '<div class="codehilite"><pre><span></span><code>&#39;\n</code></pre></div>\n'
            f'<p><span class="user-mention" data-user-id="{orig_polonius_user.id}">@Polonius</span></p>',
        )
        imported_polonius_user = UserProfile.objects.get(delivery_email=self.example_email("polonius"),
                                                         realm=imported_realm)
        imported_msg = Message.objects.get(content=special_characters_message, sender__realm=imported_realm)
        self.assertEqual(
            imported_msg.rendered_content,
            '<div class="codehilite"><pre><span></span><code>\'\n</code></pre></div>\n'
            f'<p><span class="user-mention" data-user-id="{imported_polonius_user.id}">@Polonius</span></p>',
        )

        # Check recipient_id was generated correctly for the imported users and streams.
        for user_profile in UserProfile.objects.filter(realm=imported_realm):
            self.assertEqual(user_profile.recipient_id, Recipient.objects.get(type=Recipient.PERSONAL,
                                                                              type_id=user_profile.id).id)
        for stream in Stream.objects.filter(realm=imported_realm):
            self.assertEqual(stream.recipient_id, Recipient.objects.get(type=Recipient.STREAM,
                                                                        type_id=stream.id).id)

        for huddle_object in Huddle.objects.all():
            # Huddles don't have a realm column, so we just test all Huddles for simplicity.
            self.assertEqual(huddle_object.recipient_id, Recipient.objects.get(type=Recipient.HUDDLE,
                                                                               type_id=huddle_object.id).id)

    def test_import_files_from_local(self) -> None:
        realm = Realm.objects.get(string_id='zulip')
        self._setup_export_files(realm)

        self._export_realm(realm)

        with self.settings(BILLING_ENABLED=False):
            with patch('logging.info'):
                do_import_realm(os.path.join(settings.TEST_WORKER_DIR, 'test-export'), 'test-zulip')
        imported_realm = Realm.objects.get(string_id='test-zulip')

        # Test attachments
        uploaded_file = Attachment.objects.get(realm=imported_realm)
        self.assertEqual(len(b'zulip!'), uploaded_file.size)

        attachment_file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files', uploaded_file.path_id)
        self.assertTrue(os.path.isfile(attachment_file_path))

        # Test emojis
        realm_emoji = RealmEmoji.objects.get(realm=imported_realm)
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=imported_realm.id,
            emoji_file_name=realm_emoji.file_name,
        )
        emoji_file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", emoji_path)
        self.assertTrue(os.path.isfile(emoji_file_path))

        # Test avatars
        user_email = Message.objects.all()[0].sender.email
        user_profile = UserProfile.objects.get(email=user_email, realm=imported_realm)
        avatar_path_id = user_avatar_path(user_profile) + ".original"
        avatar_file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", avatar_path_id)
        self.assertTrue(os.path.isfile(avatar_file_path))

        # Test realm icon and logo
        upload_path = upload.upload_backend.realm_avatar_and_logo_path(imported_realm)
        full_upload_path = os.path.join(settings.LOCAL_UPLOADS_DIR, upload_path)

        with get_test_image_file('img.png') as f:
            test_image_data = f.read()
        self.assertIsNotNone(test_image_data)

        with open(os.path.join(full_upload_path, "icon.original"), 'rb') as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(os.path.join(full_upload_path, "icon.png")))
        self.assertEqual(imported_realm.icon_source, Realm.ICON_UPLOADED)

        with open(os.path.join(full_upload_path, "logo.original"), 'rb') as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(os.path.join(full_upload_path, "logo.png")))
        self.assertEqual(imported_realm.logo_source, Realm.LOGO_UPLOADED)

        with open(os.path.join(full_upload_path, "night_logo.original"), 'rb') as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(os.path.join(full_upload_path, "night_logo.png")))
        self.assertEqual(imported_realm.night_logo_source, Realm.LOGO_UPLOADED)

    @use_s3_backend
    def test_import_files_from_s3(self) -> None:
        uploads_bucket, avatar_bucket = create_s3_buckets(
            settings.S3_AUTH_UPLOADS_BUCKET,
            settings.S3_AVATAR_BUCKET)

        realm = Realm.objects.get(string_id='zulip')
        self._setup_export_files(realm)

        self._export_realm(realm)
        with self.settings(BILLING_ENABLED=False):
            with patch('logging.info'):
                do_import_realm(os.path.join(settings.TEST_WORKER_DIR, 'test-export'), 'test-zulip')
        imported_realm = Realm.objects.get(string_id='test-zulip')
        with get_test_image_file('img.png') as f:
            test_image_data = f.read()

        # Test attachments
        uploaded_file = Attachment.objects.get(realm=imported_realm)
        self.assertEqual(len(b'zulip!'), uploaded_file.size)

        attachment_content = uploads_bucket.Object(uploaded_file.path_id).get()['Body'].read()
        self.assertEqual(b"zulip!", attachment_content)

        # Test emojis
        realm_emoji = RealmEmoji.objects.get(realm=imported_realm)
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=imported_realm.id,
            emoji_file_name=realm_emoji.file_name,
        )
        emoji_key = avatar_bucket.Object(emoji_path)
        self.assertIsNotNone(emoji_key.get()['Body'].read())
        self.assertEqual(emoji_key.key, emoji_path)

        # Test avatars
        user_email = Message.objects.all()[0].sender.email
        user_profile = UserProfile.objects.get(email=user_email, realm=imported_realm)
        avatar_path_id = user_avatar_path(user_profile) + ".original"
        original_image_key = avatar_bucket.Object(avatar_path_id)
        self.assertEqual(original_image_key.key, avatar_path_id)
        image_data = avatar_bucket.Object(avatar_path_id).get()['Body'].read()
        self.assertEqual(image_data, test_image_data)

        # Test realm icon and logo
        upload_path = upload.upload_backend.realm_avatar_and_logo_path(imported_realm)

        original_icon_path_id = os.path.join(upload_path, "icon.original")
        original_icon_key = avatar_bucket.Object(original_icon_path_id)
        self.assertEqual(original_icon_key.get()['Body'].read(), test_image_data)
        resized_icon_path_id = os.path.join(upload_path, "icon.png")
        resized_icon_key = avatar_bucket.Object(resized_icon_path_id)
        self.assertEqual(resized_icon_key.key, resized_icon_path_id)
        self.assertEqual(imported_realm.icon_source, Realm.ICON_UPLOADED)

        original_logo_path_id = os.path.join(upload_path, "logo.original")
        original_logo_key = avatar_bucket.Object(original_logo_path_id)
        self.assertEqual(original_logo_key.get()['Body'].read(), test_image_data)
        resized_logo_path_id = os.path.join(upload_path, "logo.png")
        resized_logo_key = avatar_bucket.Object(resized_logo_path_id)
        self.assertEqual(resized_logo_key.key, resized_logo_path_id)
        self.assertEqual(imported_realm.logo_source, Realm.LOGO_UPLOADED)

        night_logo_original_path_id = os.path.join(upload_path, "night_logo.original")
        night_logo_original_key = avatar_bucket.Object(night_logo_original_path_id)
        self.assertEqual(night_logo_original_key.get()['Body'].read(), test_image_data)
        resized_night_logo_path_id = os.path.join(upload_path, "night_logo.png")
        resized_night_logo_key = avatar_bucket.Object(resized_night_logo_path_id)
        self.assertEqual(resized_night_logo_key.key, resized_night_logo_path_id)
        self.assertEqual(imported_realm.night_logo_source, Realm.LOGO_UPLOADED)

    def test_get_incoming_message_ids(self) -> None:
        import_dir = os.path.join(settings.DEPLOY_ROOT, "zerver", "tests", "fixtures", "import_fixtures")
        message_ids = get_incoming_message_ids(
            import_dir=import_dir,
            sort_by_date=True,
        )

        self.assertEqual(message_ids, [888, 999, 555])

        message_ids = get_incoming_message_ids(
            import_dir=import_dir,
            sort_by_date=False,
        )

        self.assertEqual(message_ids, [555, 888, 999])

    def test_plan_type(self) -> None:
        realm = get_realm('zulip')
        do_change_plan_type(realm, Realm.LIMITED)

        self._setup_export_files(realm)
        self._export_realm(realm)

        with patch('logging.info'):
            with self.settings(BILLING_ENABLED=True):
                realm = do_import_realm(os.path.join(settings.TEST_WORKER_DIR, 'test-export'),
                                        'test-zulip-1')
                self.assertEqual(realm.plan_type, Realm.LIMITED)
                self.assertEqual(realm.max_invites, 100)
                self.assertEqual(realm.upload_quota_gb, 5)
                self.assertEqual(realm.message_visibility_limit, 10000)
                self.assertTrue(RealmAuditLog.objects.filter(
                    realm=realm, event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED).exists())
            with self.settings(BILLING_ENABLED=False):
                realm = do_import_realm(os.path.join(settings.TEST_WORKER_DIR, 'test-export'),
                                        'test-zulip-2')
                self.assertEqual(realm.plan_type, Realm.SELF_HOSTED)
                self.assertEqual(realm.max_invites, 100)
                self.assertEqual(realm.upload_quota_gb, None)
                self.assertEqual(realm.message_visibility_limit, None)
                self.assertTrue(RealmAuditLog.objects.filter(
                    realm=realm, event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED).exists())
