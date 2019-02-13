# -*- coding: utf-8 -*-

from django.conf import settings

import os
import shutil
import ujson

from mock import patch
from typing import Any, Dict, List, Set, Optional, Tuple, Callable, \
    FrozenSet

from zerver.lib.export import (
    do_export_realm,
    export_usermessages_batch,
    do_export_user,
)
from zerver.lib.import_realm import (
    do_import_realm,
    get_incoming_message_ids,
)
from zerver.lib.avatar_hash import (
    user_avatar_path,
)
from zerver.lib.upload import (
    claim_attachment,
    upload_message_file,
    upload_emoji_image,
    upload_avatar_image,
)
from zerver.lib.utils import (
    query_chunker,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_helpers import (
    use_s3_backend,
    create_s3_buckets,
)

from zerver.lib.topic_mutes import (
    add_topic_mute,
)
from zerver.lib.bot_lib import (
    StateHandler,
)
from zerver.lib.bot_config import (
    set_bot_config
)
from zerver.lib.actions import (
    do_create_user,
)

from zerver.lib.test_runner import slow

from zerver.models import (
    Message,
    Realm,
    Stream,
    UserProfile,
    Subscription,
    Attachment,
    RealmEmoji,
    Recipient,
    UserMessage,
    CustomProfileField,
    CustomProfileFieldValue,
    RealmAuditLog,
    Huddle,
    UserHotspot,
    MutedTopic,
    UserGroup,
    UserGroupMembership,
    BotStorageData,
    BotConfigData,
    get_active_streams,
    get_realm,
    get_stream,
    get_stream_recipient,
    get_personal_recipient,
    get_huddle_hash,
)

from zerver.lib.test_helpers import (
    get_test_image_file,
)

def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

class QueryUtilTest(ZulipTestCase):
    def _create_messages(self) -> None:
        for email in [self.example_email('cordelia'),
                      self.example_email('hamlet'),
                      self.example_email('iago')]:
            for _ in range(5):
                self.send_personal_message(email, self.example_email('othello'))

    @slow('creates lots of data')
    def test_query_chunker(self) -> None:
        self._create_messages()

        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')

        def get_queries() -> List[Any]:
            queries = [
                Message.objects.filter(sender_id=cordelia.id),
                Message.objects.filter(sender_id=hamlet.id),
                Message.objects.exclude(sender_id__in=[cordelia.id, hamlet.id])
            ]
            return queries

        for query in get_queries():
            # For our test to be meaningful, we want non-empty queries
            # at first
            assert len(list(query)) > 0

        queries = get_queries()

        all_msg_ids = set()  # type: Set[int]
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
            len(Message.objects.filter(sender_id__in=[cordelia.id, hamlet.id]))
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
            len(Message.objects.exclude(sender_id=cordelia.id))
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
        first_chunk = next(chunker)  # type: ignore
        self.assertEqual(len(first_chunk), 10)
        self.assertEqual(len(all_msg_ids), 10)
        expected_msg = Message.objects.all()[0:10][5]
        actual_msg = first_chunk[5]
        self.assertEqual(actual_msg.content, expected_msg.content)
        self.assertEqual(actual_msg.sender_id, expected_msg.sender_id)


class ImportExportTest(ZulipTestCase):

    def setUp(self) -> None:
        rm_tree(settings.LOCAL_UPLOADS_DIR)

    def _make_output_dir(self) -> str:
        output_dir = 'var/test-export'
        rm_tree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _export_realm(self, realm: Realm, exportable_user_ids: Optional[Set[int]]=None) -> Dict[str, Any]:
        output_dir = self._make_output_dir()
        with patch('logging.info'), patch('zerver.lib.export.create_soft_link'):
            do_export_realm(
                realm=realm,
                output_dir=output_dir,
                threads=0,
                exportable_user_ids=exportable_user_ids,
            )
            # TODO: Process the second partial file, which can be created
            #       for certain edge cases.
            export_usermessages_batch(
                input_path=os.path.join(output_dir, 'messages-000001.json.partial'),
                output_path=os.path.join(output_dir, 'messages-000001.json')
            )

        def read_file(fn: str) -> Any:
            full_fn = os.path.join(output_dir, fn)
            with open(full_fn) as f:
                return ujson.load(f)

        result = {}
        result['realm'] = read_file('realm.json')
        result['attachment'] = read_file('attachment.json')
        result['message'] = read_file('messages-000001.json')
        result['uploads_dir'] = os.path.join(output_dir, 'uploads')
        result['uploads_dir_records'] = read_file(os.path.join('uploads', 'records.json'))
        result['emoji_dir'] = os.path.join(output_dir, 'emoji')
        result['emoji_dir_records'] = read_file(os.path.join('emoji', 'records.json'))
        result['avatar_dir'] = os.path.join(output_dir, 'avatars')
        result['avatar_dir_records'] = read_file(os.path.join('avatars', 'records.json'))
        return result

    def _setup_export_files(self) -> Tuple[str, str, str, bytes]:
        realm = Realm.objects.get(string_id='zulip')
        message = Message.objects.all()[0]
        user_profile = message.sender
        url = upload_message_file(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)
        attachment_path_id = url.replace('/user_uploads/', '')
        claim_attachment(
            user_profile=user_profile,
            path_id=attachment_path_id,
            message=message,
            is_message_realm_public=True
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
        test_image = open(get_test_image_file('img.png').name, 'rb').read()
        message.sender.avatar_source = 'U'
        message.sender.save()

        return attachment_path_id, emoji_path, original_avatar_path_id, test_image

    """
    Tests for export
    """

    def test_export_files_from_local(self) -> None:
        realm = Realm.objects.get(string_id='zulip')
        path_id, emoji_path, original_avatar_path_id, test_image = self._setup_export_files()
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
        self.assertEqual(records[0]['path'], '1/emoji/images/1.png')
        self.assertEqual(records[0]['s3_path'], '1/emoji/images/1.png')

        # Test avatars
        fn = os.path.join(full_data['avatar_dir'], original_avatar_path_id)
        fn_data = open(fn, 'rb').read()
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
        attachment_path_id, emoji_path, original_avatar_path_id, test_image = self._setup_export_files()
        full_data = self._export_realm(realm)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], attachment_path_id)

        def check_variable_type(user_profile_id: int, realm_id: int) -> None:
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
        check_variable_type(records[0]['user_profile_id'], records[0]['realm_id'])

        # Test emojis
        fn = os.path.join(full_data['emoji_dir'], emoji_path)
        fn = fn.replace('1.png', '')
        self.assertIn('1.png', os.listdir(fn))
        records = full_data['emoji_dir_records']
        self.assertEqual(records[0]['file_name'], '1.png')
        self.assertTrue('last_modified' in records[0])
        self.assertEqual(records[0]['path'], '1/emoji/images/1.png')
        self.assertEqual(records[0]['s3_path'], '1/emoji/images/1.png')
        check_variable_type(records[0]['user_profile_id'], records[0]['realm_id'])

        # Test avatars
        fn = os.path.join(full_data['avatar_dir'], original_avatar_path_id)
        fn_data = open(fn, 'rb').read()
        self.assertEqual(fn_data, test_image)
        records = full_data['avatar_dir_records']
        record_path = [record['path'] for record in records]
        record_s3_path = [record['s3_path'] for record in records]
        self.assertIn(original_avatar_path_id, record_path)
        self.assertIn(original_avatar_path_id, record_s3_path)
        check_variable_type(records[0]['user_profile_id'], records[0]['realm_id'])

    def test_zulip_realm(self) -> None:
        realm = Realm.objects.get(string_id='zulip')
        realm_emoji = RealmEmoji.objects.get(realm=realm)
        realm_emoji.delete()
        full_data = self._export_realm(realm)
        realm_emoji.save()

        data = full_data['realm']
        self.assertEqual(len(data['zerver_userprofile_crossrealm']), 0)
        self.assertEqual(len(data['zerver_userprofile_mirrordummy']), 0)

        def get_set(table: str, field: str) -> Set[str]:
            values = set(r[field] for r in data[table])
            # print('set(%s)' % sorted(values))
            return values

        def find_by_id(table: str, db_id: int) -> Dict[str, Any]:
            return [
                r for r in data[table]
                if r['id'] == db_id][0]

        exported_user_emails = get_set('zerver_userprofile', 'email')
        self.assertIn(self.example_email('cordelia'), exported_user_emails)
        self.assertIn('default-bot@zulip.com', exported_user_emails)
        self.assertIn('emailgateway@zulip.com', exported_user_emails)

        exported_streams = get_set('zerver_stream', 'name')
        self.assertEqual(
            exported_streams,
            set([u'Denmark', u'Rome', u'Scotland', u'Venice', u'Verona'])
        )

        data = full_data['message']
        um = UserMessage.objects.all()[0]
        exported_um = find_by_id('zerver_usermessage', um.id)
        self.assertEqual(exported_um['message'], um.message_id)
        self.assertEqual(exported_um['user_profile'], um.user_profile_id)

        exported_message = find_by_id('zerver_message', um.message_id)
        self.assertEqual(exported_message['content'], um.message.content)

        # TODO, extract get_set/find_by_id, so we can split this test up

        # Now, restrict users
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        user_ids = set([cordelia.id, hamlet.id])

        realm_emoji = RealmEmoji.objects.get(realm=realm)
        realm_emoji.delete()
        full_data = self._export_realm(realm, exportable_user_ids=user_ids)
        realm_emoji.save()

        data = full_data['realm']
        exported_user_emails = get_set('zerver_userprofile', 'email')
        self.assertIn(self.example_email('cordelia'), exported_user_emails)
        self.assertIn(self.example_email('hamlet'), exported_user_emails)
        self.assertNotIn('default-bot@zulip.com', exported_user_emails)
        self.assertNotIn(self.example_email('iago'), exported_user_emails)

        dummy_user_emails = get_set('zerver_userprofile_mirrordummy', 'email')
        self.assertIn(self.example_email('iago'), dummy_user_emails)
        self.assertNotIn(self.example_email('cordelia'), dummy_user_emails)

    def test_export_single_user(self) -> None:
        output_dir = self._make_output_dir()
        cordelia = self.example_user('cordelia')

        with patch('logging.info'):
            do_export_user(cordelia, output_dir)

        def read_file(fn: str) -> Any:
            full_fn = os.path.join(output_dir, fn)
            with open(full_fn) as f:
                return ujson.load(f)

        def get_set(data: List[Dict[str, Any]], field: str) -> Set[str]:
            values = set(r[field] for r in data)
            # print('set(%s)' % sorted(values))
            return values

        messages = read_file('messages-000001.json')
        user = read_file('user.json')

        exported_user_id = get_set(user['zerver_userprofile'], 'id')
        self.assertEqual(exported_user_id, set([cordelia.id]))
        exported_user_email = get_set(user['zerver_userprofile'], 'email')
        self.assertEqual(exported_user_email, set([cordelia.email]))

        exported_recipient_type_id = get_set(user['zerver_recipient'], 'type_id')
        self.assertIn(cordelia.id, exported_recipient_type_id)

        exported_stream_id = get_set(user['zerver_stream'], 'id')
        self.assertIn(list(exported_stream_id)[0], exported_recipient_type_id)

        exported_recipient_id = get_set(user['zerver_recipient'], 'id')
        exported_subscription_recipient = get_set(user['zerver_subscription'], 'recipient')
        self.assertEqual(exported_recipient_id, exported_subscription_recipient)

        exported_messages_recipient = get_set(messages['zerver_message'], 'recipient')
        self.assertIn(list(exported_messages_recipient)[0], exported_recipient_id)

    """
    Tests for import_realm
    """
    def test_import_realm(self) -> None:

        original_realm = Realm.objects.get(string_id='zulip')
        RealmEmoji.objects.get(realm=original_realm).delete()
        # data to test import of huddles
        huddle = [
            self.example_email('hamlet'),
            self.example_email('othello')
        ]
        self.send_huddle_message(
            self.example_email('cordelia'), huddle, 'test huddle message'
        )

        # data to test import of hotspots
        sample_user = self.example_user('hamlet')

        UserHotspot.objects.create(
            user=sample_user, hotspot='intro_streams'
        )

        # data to test import of muted topic
        stream = get_stream(u'Verona', original_realm)
        add_topic_mute(
            user_profile=sample_user,
            stream_id=stream.id,
            recipient_id=get_stream_recipient(stream.id).id,
            topic_name=u'Verona2')

        # data to test import of botstoragedata and botconfigdata
        bot_profile = do_create_user(
            email="bot-1@zulip.com",
            password="test",
            realm=original_realm,
            full_name="bot",
            short_name="bot",
            bot_type=UserProfile.EMBEDDED_BOT,
            bot_owner=sample_user)
        storage = StateHandler(bot_profile)
        storage.put('some key', 'some value')

        set_bot_config(bot_profile, 'entry 1', 'value 1')

        self._export_realm(original_realm)

        with patch('logging.info'):
            with self.settings(BILLING_ENABLED=False):
                do_import_realm('var/test-export', 'test-zulip')

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
            lambda r: {user.email for user in r.get_admin_users()}
        )

        assert_realm_values(
            lambda r: {user.email for user in r.get_active_users()}
        )

        # test stream
        assert_realm_values(
            lambda r: {stream.name for stream in get_active_streams(r)}
        )

        # test recipients
        def get_recipient_stream(r: Realm) -> Stream:
            return get_stream_recipient(
                Stream.objects.get(name='Verona', realm=r).id
            )

        def get_recipient_user(r: Realm) -> UserProfile:
            return get_personal_recipient(
                UserProfile.objects.get(full_name='Iago', realm=r).id
            )

        assert_realm_values(lambda r: get_recipient_stream(r).type)
        assert_realm_values(lambda r: get_recipient_user(r).type)

        # test subscription
        def get_subscribers(recipient: Recipient) -> Set[str]:
            subscriptions = Subscription.objects.filter(recipient=recipient)
            users = {sub.user_profile.email for sub in subscriptions}
            return users

        assert_realm_values(
            lambda r: get_subscribers(get_recipient_stream(r))
        )

        assert_realm_values(
            lambda r: get_subscribers(get_recipient_user(r))
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
                user_id_list = ujson.loads(field_value.value)
                return {get_email(user_id) for user_id in user_id_list}

            def custom_profile_field_values_for(fields: List[CustomProfileField]) -> Set[FrozenSet[str]]:
                user_emails = set()  # type: Set[FrozenSet[str]]
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

        # test huddles
        def get_huddle_hashes(r: str) -> str:
            short_names = ['cordelia', 'hamlet', 'othello']
            user_id_list = [UserProfile.objects.get(realm=r, short_name=name).id for name in short_names]
            huddle_hash = get_huddle_hash(user_id_list)
            return huddle_hash

        assert_realm_values(get_huddle_hashes, equal=False)

        def get_huddle_message(r: str) -> str:
            huddle_hash = get_huddle_hashes(r)
            huddle_id = Huddle.objects.get(huddle_hash=huddle_hash).id
            huddle_recipient = Recipient.objects.get(type_id=huddle_id, type=3)
            huddle_message = Message.objects.get(recipient=huddle_recipient)
            return huddle_message.content

        assert_realm_values(get_huddle_message)
        self.assertEqual(get_huddle_message(imported_realm), 'test huddle message')

        # test userhotspot
        def get_user_hotspots(r: str) -> Set[str]:
            user_profile = UserProfile.objects.get(realm=r, short_name='hamlet')
            hotspots = UserHotspot.objects.filter(user=user_profile)
            user_hotspots = {hotspot.hotspot for hotspot in hotspots}
            return user_hotspots

        assert_realm_values(get_user_hotspots)

        # test muted topics
        def get_muted_topics(r: Realm) -> Set[str]:
            user_profile = UserProfile.objects.get(realm=r, short_name='hamlet')
            muted_topics = MutedTopic.objects.filter(user_profile=user_profile)
            topic_names = {muted_topic.topic_name for muted_topic in muted_topics}
            return topic_names

        assert_realm_values(get_muted_topics)

        # test usergroups
        assert_realm_values(
            lambda r: {group.name for group in UserGroup.objects.filter(realm=r)}
        )

        def get_user_membership(r: str) -> Set[str]:
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

    def test_import_files_from_local(self) -> None:

        realm = Realm.objects.get(string_id='zulip')
        self._setup_export_files()
        self._export_realm(realm)

        with patch('logging.info'):
            do_import_realm('var/test-export', 'test-zulip')
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

    @use_s3_backend
    def test_import_files_from_s3(self) -> None:
        uploads_bucket, avatar_bucket = create_s3_buckets(
            settings.S3_AUTH_UPLOADS_BUCKET,
            settings.S3_AVATAR_BUCKET)

        realm = Realm.objects.get(string_id='zulip')
        self._setup_export_files()
        self._export_realm(realm)
        with patch('logging.info'):
            do_import_realm('var/test-export', 'test-zulip')
        imported_realm = Realm.objects.get(string_id='test-zulip')
        test_image_data = open(get_test_image_file('img.png').name, 'rb').read()

        # Test attachments
        uploaded_file = Attachment.objects.get(realm=imported_realm)
        self.assertEqual(len(b'zulip!'), uploaded_file.size)

        attachment_content = uploads_bucket.get_key(uploaded_file.path_id).get_contents_as_string()
        self.assertEqual(b"zulip!", attachment_content)

        # Test emojis
        realm_emoji = RealmEmoji.objects.get(realm=imported_realm)
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=imported_realm.id,
            emoji_file_name=realm_emoji.file_name,
        )
        emoji_key = avatar_bucket.get_key(emoji_path)
        self.assertIsNotNone(emoji_key)
        self.assertEqual(emoji_key.key, emoji_path)

        # Test avatars
        user_email = Message.objects.all()[0].sender.email
        user_profile = UserProfile.objects.get(email=user_email, realm=imported_realm)
        avatar_path_id = user_avatar_path(user_profile) + ".original"
        original_image_key = avatar_bucket.get_key(avatar_path_id)
        self.assertEqual(original_image_key.key, avatar_path_id)
        image_data = original_image_key.get_contents_as_string()
        self.assertEqual(image_data, test_image_data)

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
        realm.plan_type = Realm.STANDARD
        realm.save(update_fields=['plan_type'])

        self._setup_export_files()
        self._export_realm(realm)

        with patch('logging.info'):
            with self.settings(BILLING_ENABLED=True):
                realm = do_import_realm('var/test-export', 'test-zulip-1')
                self.assertTrue(realm.plan_type, Realm.LIMITED)
                self.assertTrue(RealmAuditLog.objects.filter(
                    realm=realm, event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED).exists())
            with self.settings(BILLING_ENABLED=False):
                realm = do_import_realm('var/test-export', 'test-zulip-2')
                self.assertTrue(realm.plan_type, Realm.SELF_HOSTED)
                self.assertTrue(RealmAuditLog.objects.filter(
                    realm=realm, event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED).exists())
