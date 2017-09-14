# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from django.db import migrations, models

from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.upload import attachment_url_re, attachment_url_to_path_id


def check_and_create_attachments(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    STREAM = 2
    Message = apps.get_model('zerver', 'Message')
    Attachment = apps.get_model('zerver', 'Attachment')
    Stream = apps.get_model('zerver', 'Stream')
    for message in Message.objects.filter(has_attachment=True, attachment=None):
        attachment_url_list = attachment_url_re.findall(message.content)
        for url in attachment_url_list:
            path_id = attachment_url_to_path_id(url)
            user_profile = message.sender
            is_message_realm_public = False
            if message.recipient.type == STREAM:
                stream = Stream.objects.get(id=message.recipient.type_id)
                is_message_realm_public = not stream.invite_only and not stream.realm.is_zephyr_mirror_realm

            if path_id is not None:
                attachment = Attachment.objects.create(
                    file_name=os.path.basename(path_id), path_id=path_id, owner=user_profile,
                    realm=user_profile.realm, is_realm_public=is_message_realm_public)
                attachment.messages.add(message)


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0040_realm_authentication_methods'),
    ]

    operations = [
        # The TextField change was originally in the next migration,
        # but because it fixes a problem that causes the RunPython
        # part of this migration to crash, we've copied it here.
        migrations.AlterField(
            model_name='attachment',
            name='file_name',
            field=models.TextField(db_index=True),
        ),
        migrations.RunPython(check_and_create_attachments)
    ]
