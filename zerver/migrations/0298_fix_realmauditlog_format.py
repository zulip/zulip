# Generated by Django 2.2.14 on 2020-08-07 19:13

import json

from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def update_realmauditlog_values(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    """
    This migration fixes two issues with the RealmAuditLog format for certain event types:
    * The notifications_stream and signup_notifications_stream fields had the
      Stream objects passed into `ujson.dumps()` and thus marshalled as a giant
      JSON object, when the intent was to store the stream ID.
    * The default_sending_stream would also been marshalled wrong, but are part
      of a feature that nobody should be using, so we simply assert that's the case.
    * Changes the structure of the extra_data JSON dictionaries for those
      RealmAuditLog entries with a sub-property field from:
      {
          OLD_VALUE: {"property": property, "value": old_value},
          NEW_VALUE: {"property": property, "value": new_value},
      }

      to the more natural:

      {
          OLD_VALUE: old_value,
          NEW_VALUE: new_value,
          "property": property,
      }
    """
    RealmAuditLog = apps.get_model('zerver', 'RealmAuditLog')
    # Constants from models.py
    USER_DEFAULT_SENDING_STREAM_CHANGED = 129
    USER_DEFAULT_REGISTER_STREAM_CHANGED = 130
    USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED = 131
    USER_NOTIFICATION_SETTINGS_CHANGED = 132
    REALM_PROPERTY_CHANGED = 207
    SUBSCRIPTION_PROPERTY_CHANGED = 304
    OLD_VALUE = '1'
    NEW_VALUE = '2'

    unlikely_event_types = [
        USER_DEFAULT_SENDING_STREAM_CHANGED,
        USER_DEFAULT_REGISTER_STREAM_CHANGED,
        USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED,
    ]
    # These 3 event types are the ones that used a format with
    # OLD_VALUE containing a dictionary with a `property` key.
    affected_event_types = [
        REALM_PROPERTY_CHANGED,
        USER_NOTIFICATION_SETTINGS_CHANGED,
        SUBSCRIPTION_PROPERTY_CHANGED,
    ]
    improperly_marshalled_properties = [
        'notifications_stream',
        'signup_notifications_stream',
    ]

    # These are also corrupted but are part of a feature nobody uses,
    # so it's not worth writing code to fix them.
    assert not RealmAuditLog.objects.filter(event_type__in=unlikely_event_types).exists()

    for ra in RealmAuditLog.objects.filter(event_type__in=affected_event_types):
        extra_data = json.loads(ra.extra_data)
        old_key = extra_data[OLD_VALUE]
        new_key = extra_data[NEW_VALUE]

        # Skip any already-migrated values in case we're running this
        # migration a second time.
        if not isinstance(old_key, dict) and not isinstance(new_key, dict):
            continue
        if 'value' not in old_key or 'value' not in new_key:
            continue

        old_value = old_key["value"]
        new_value = new_key["value"]
        prop = old_key["property"]

        # The `authentication_methods` key is the only event whose
        # action value type is expected to be a dictionary.  That
        # property is marshalled properly but still wants the second
        # migration below.
        if prop != 'authentication_methods':
            # For the other properties, we have `stream` rather than `stream['id']`
            # in the original extra_data object; the fix is simply to extract
            # the intended ID field via `value = value['id']`.
            if isinstance(old_value, dict):
                assert prop in improperly_marshalled_properties
                old_value = old_value['id']
            if isinstance(new_value, dict):
                assert prop in improperly_marshalled_properties
                new_value = new_value['id']

        # Sanity check that the original event has exactly the keys we expect.
        assert set(extra_data.keys()) <= {OLD_VALUE, NEW_VALUE}

        ra.extra_data = json.dumps({
            OLD_VALUE: old_value,
            NEW_VALUE: new_value,
            "property": prop,
        })
        ra.save(update_fields=["extra_data"])


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0297_draft'),
    ]

    operations = [
        migrations.RunPython(update_realmauditlog_values,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
