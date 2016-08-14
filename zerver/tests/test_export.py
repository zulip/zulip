# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from django.conf import settings
from django.test import TestCase

import os
import shutil
import ujson

from mock import patch, MagicMock
from typing import Any

from zerver.lib.actions import (
    do_claim_attachments,
)

from zerver.lib.export import (
    do_export_realm,
    export_usermessages_batch,
)
from zerver.lib.upload import (
    claim_attachment,
    upload_message_image,
)
from zerver.lib.utils import mkdir_p
from zerver.models import (
    get_user_profile_by_email,
    Message,
    Realm,
    UserMessage,
)

def rm_tree(path):
    # type: (str) -> None
    if os.path.exists(path):
        shutil.rmtree(path)

class ExportTest(TestCase):

    def setUp(self):
        # type: () -> None
        rm_tree(settings.LOCAL_UPLOADS_DIR)

    def _make_output_dir(self):
        # type: () -> str
        output_dir = 'var/test-export'
        rm_tree(output_dir)
        mkdir_p(output_dir)
        return output_dir

    def _export_realm(self, domain, exportable_user_ids=None):
        # type: (str, Set[int]) -> Dict[str, Any]
        output_dir = self._make_output_dir()
        realm = Realm.objects.get(domain=domain)
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

        def read_file(fn):
            full_fn = os.path.join(output_dir, fn)
            with open(full_fn) as f:
                return ujson.load(f)

        result = {}
        result['realm'] = read_file('realm.json')
        result['attachment'] = read_file('attachment.json')
        result['message'] = read_file('message.json')
        result['uploads_dir'] = os.path.join(output_dir, 'uploads')
        return result

    def test_attachment(self):
        # type: () -> None
        message = Message.objects.all()[0]
        user_profile = message.sender
        url = upload_message_image(u'dummy.txt', u'text/plain', b'zulip!', user_profile)
        path_id = url.replace('/user_uploads/', '')
        claim_attachment(
            user_profile=user_profile,
            path_id=path_id,
            message=message,
            is_message_realm_public=True
        )

        domain = 'zulip.com'
        full_data = self._export_realm(domain=domain)

        data = full_data['attachment']
        self.assertEqual(len(data['zerver_attachment']), 1)
        record = data['zerver_attachment'][0]
        self.assertEqual(record['path_id'], path_id)

        fn = os.path.join(full_data['uploads_dir'], path_id)
        with open(fn) as f:
            self.assertEqual(f.read(), 'zulip!')

    def test_zulip_realm(self):
        # type: () -> None
        domain = 'zulip.com'
        full_data = self._export_realm(domain=domain)

        data = full_data['realm']
        self.assertEqual(len(data['zerver_userprofile_crossrealm']), 0)
        self.assertEqual(len(data['zerver_userprofile_mirrordummy']), 0)

        def get_set(table, field):
            # type: (str, str) -> Set[str]
            values = set(r[field] for r in data[table])
            # print('set(%s)' % sorted(values))
            return values

        def find_by_id(table, db_id):
            # type: (str) -> Dict[str, Any]
            return [
                r for r in data[table]
                if r['id'] == db_id][0]


        exported_user_emails = get_set('zerver_userprofile', 'email')
        self.assertIn('cordelia@zulip.com', exported_user_emails)
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
        cordelia = get_user_profile_by_email('cordelia@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        user_ids = set([cordelia.id, hamlet.id])

        full_data = self._export_realm(
            domain=domain,
            exportable_user_ids=user_ids
        )
        data = full_data['realm']
        exported_user_emails = get_set('zerver_userprofile', 'email')
        self.assertIn('cordelia@zulip.com', exported_user_emails)
        self.assertIn('hamlet@zulip.com', exported_user_emails)
        self.assertNotIn('default-bot@zulip.com', exported_user_emails)
        self.assertNotIn('iago@zulip.com', exported_user_emails)

        dummy_user_emails = get_set('zerver_userprofile_mirrordummy', 'email')
        self.assertIn('iago@zulip.com', dummy_user_emails)
        self.assertNotIn('cordelia@zulip.com', dummy_user_emails)

