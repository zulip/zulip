from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F, Q


def fix_invalid_emails(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Users deleted prior to the fix in 208c0c303405 have invalid
    addresses of the form deleteduser123@https://zulip.example.com.
    0439_fix_deleteduser_email repaired the delivery_email field, but
    not the email field; on realms whose (then realm-level)
    email_address_visibility setting was "everyone", the email field
    held the same invalid address and should equal delivery_email.
    (On other realms, the dummy's email field got a valid
    user{id}@<fake domain> address, which this filter won't match.)
    """

    UserProfile = apps.get_model("zerver", "UserProfile")
    UserProfile.objects.filter(is_active=False).filter(
        Q(email__icontains="@https://") | Q(email__icontains="@http://")
    ).update(email=F("delivery_email"))


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0804_backfill_user_created_audit_logs"),
    ]

    operations = [
        migrations.RunPython(
            fix_invalid_emails, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
