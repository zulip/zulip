# -*- coding: utf-8 -*-

from django.conf import settings

import os
import shutil
import ujson
import io
from PIL import Image

from mock import patch, MagicMock
from typing import Any, Dict, List, Set, Optional
from boto.s3.connection import Location, S3Connection

from zerver.lib.export import (
    do_export_realm,
    export_files_from_s3,
    export_usermessages_batch,
    do_export_user,
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
)

from zerver.lib.test_runner import slow

from zerver.models import (
    Message,
    Realm,
    Attachment,
    RealmEmoji,
    Recipient,
    UserMessage,
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


class ExportTest(ZulipTestCase):

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
                output_path=os.path.join(output_dir, 'message.json')
            )

        def read_file(fn: str) -> Any:
            full_fn = os.path.join(output_dir, fn)
            with open(full_fn) as f:
                return ujson.load(f)

        result = {}
        result['realm'] = read_file('realm.json')
        result['attachment'] = read_file('attachment.json')
        result['message'] = read_file('message.json')
        result['uploads_dir'] = os.path.join(output_dir, 'uploads')
        result['emoji_dir'] = os.path.join(output_dir, 'emoji')
        result['avatar_dir'] = os.path.join(output_dir, 'avatars')
        return result

    def test_export_files_from_local(self) -> None:
        message = Message.objects.all()[0]
        user_profile = message.sender
        url = upload_message_file(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)
        path_id = url.replace('/user_uploads/', '')
        claim_attachment(
            user_profile=user_profile,
            path_id=path_id,
            message=message,
            is_message_realm_public=True
        )
        avatar_path_id = user_avatar_path(user_profile)
        original_avatar_path_id = avatar_path_id + ".original"

        realm = Realm.objects.get(string_id='zulip')
        with get_test_image_file('img.png') as img_file:
            upload_emoji_image(img_file, '1.png', user_profile)
        with get_test_image_file('img.png') as img_file:
            upload_avatar_image(img_file, user_profile, user_profile)
        test_image = open(get_test_image_file('img.png').name, 'rb').read()
        message.sender.avatar_source = 'U'
        message.sender.save()

        full_data = self._export_realm(realm)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], path_id)

        # Test uploads
        fn = os.path.join(full_data['uploads_dir'], path_id)
        with open(fn) as f:
            self.assertEqual(f.read(), 'zulip!')

        # Test emojis
        fn = os.path.join(full_data['emoji_dir'],
                          RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm.id, emoji_file_name='1.png'))
        fn = fn.replace('1.png', '')
        self.assertEqual('1.png', os.listdir(fn)[0])

        # Test avatars
        fn = os.path.join(full_data['avatar_dir'], original_avatar_path_id)
        fn_data = open(fn, 'rb').read()
        self.assertEqual(fn_data, test_image)

    @use_s3_backend
    def test_export_files_from_s3(self) -> None:
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)
        conn.create_bucket(settings.S3_AVATAR_BUCKET)

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

        full_data = self._export_realm(realm)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], attachment_path_id)

        # Test uploads
        fields = attachment_path_id.split('/')
        fn = os.path.join(full_data['uploads_dir'], os.path.join(fields[1], fields[2]))
        with open(fn) as f:
            self.assertEqual(f.read(), 'zulip!')

        # Test emojis
        fn = os.path.join(full_data['emoji_dir'], emoji_path)
        fn = fn.replace('1.png', '')
        self.assertIn('1.png', os.listdir(fn))

        # Test avatars
        fn = os.path.join(full_data['avatar_dir'], original_avatar_path_id)
        fn_data = open(fn, 'rb').read()
        self.assertEqual(fn_data, test_image)

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
