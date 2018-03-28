# -*- coding: utf-8 -*-

from django.conf import settings
from django.test import TestCase

import os
import shutil
import ujson

from mock import patch, MagicMock
from typing import Any, Dict, List, Set, Optional

from zerver.lib.actions import (
    do_claim_attachments,
)

from zerver.lib.export import (
    do_export_realm,
    export_usermessages_batch,
)
from zerver.lib.upload import (
    claim_attachment,
    upload_message_file,
)
from zerver.lib.utils import (
    query_chunker,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.lib.test_runner import slow

from zerver.models import (
    Message,
    Realm,
    Recipient,
    UserMessage,
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
        return result

    def test_attachment(self) -> None:
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

        realm = Realm.objects.get(string_id='zulip')
        full_data = self._export_realm(realm)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], path_id)

        fn = os.path.join(full_data['uploads_dir'], path_id)
        with open(fn) as f:
            self.assertEqual(f.read(), 'zulip!')

    def test_zulip_realm(self) -> None:
        realm = Realm.objects.get(string_id='zulip')
        full_data = self._export_realm(realm)

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

        full_data = self._export_realm(realm, exportable_user_ids=user_ids)
        data = full_data['realm']
        exported_user_emails = get_set('zerver_userprofile', 'email')
        self.assertIn(self.example_email('cordelia'), exported_user_emails)
        self.assertIn(self.example_email('hamlet'), exported_user_emails)
        self.assertNotIn('default-bot@zulip.com', exported_user_emails)
        self.assertNotIn(self.example_email('iago'), exported_user_emails)

        dummy_user_emails = get_set('zerver_userprofile_mirrordummy', 'email')
        self.assertIn(self.example_email('iago'), dummy_user_emails)
        self.assertNotIn(self.example_email('cordelia'), dummy_user_emails)
