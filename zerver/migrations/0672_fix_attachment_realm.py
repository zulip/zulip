import re

from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_attachment_realm(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    Attachment = apps.get_model("zerver", "Attachment")
    ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")

    if not Realm.objects.exists():
        return

    internal_realm = Realm.objects.get(string_id=settings.SYSTEM_BOT_REALM)

    print()
    for model in [Attachment, ArchivedAttachment]:
        for attachment in model.objects.filter(realm_id=internal_realm.id).order_by("id"):
            message = attachment.messages.only("realm_id").first()
            if message is not None:
                realm_id = message.realm_id
            else:
                # If attachment.messages is empty, try to infer the realm from path_id.
                # The s3 backend set the path_id based on the correct realm, while the local
                # storage backend formed path_id based on sender's realm (which was wrong
                # for these attachments we're fixing, since the sender was a cross realm bot).
                # We don't need to complicate the logic here with conditioning on the backend
                # because worst case scenario, this just infers the realm to be the system bot
                # realm, thus not changing anything at all.
                matches = re.findall(r"^(\d+)\/", attachment.path_id)
                if not matches:
                    print(
                        f"No realm_id found in path_id '{attachment.path_id}' of attachment {attachment.id}"
                    )
                    continue

                try:
                    realm_id = int(matches[0])
                    if not Realm.objects.filter(id=realm_id).exists():
                        # If the realm doesn't exist (e.g. due to deletion), we can't do anything.
                        continue
                except ValueError:
                    # Don't do anything if path_id doesn't start with a sensible realm id.
                    print(
                        f"Encountered ValueError for realm_id {realm_id} inferred from path_id of attachment {attachment.id}"
                    )
                    continue

            if realm_id == attachment.realm_id:
                # It's already correct, nothing to do.
                continue

            print(
                f"Fixing incorrect realm for {model.__name__} {attachment.id} ({attachment.realm_id} => {realm_id})"
            )
            attachment.realm_id = realm_id
            attachment.save(update_fields=["realm_id"])


class Migration(migrations.Migration):
    """
    Old messages with attachments, sent by cross-realm bots, didn't have
    the realm set correctly to the target realm, this migration fixes it
    by looking at the messages linking to the attachment and setting the realm
    based on the recipient.
    """

    atomic = False

    dependencies = [
        ("zerver", "0671_remove_realm_wildcard_mention_policy"),
    ]

    operations = [
        migrations.RunPython(
            fix_attachment_realm,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
