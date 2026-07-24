from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_display_in_profile_summary_for_first_pronoun_field(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Ensure the first pronoun field in each realm has display_in_profile_summary=True.
    This matches the UI behavior where the first pronoun field checkbox is forced
    to be checked and disabled.
    """
    Realm = apps.get_model("zerver", "Realm")
    CustomProfileField = apps.get_model("zerver", "CustomProfileField")

    PRONOUNS = 8

    for realm in Realm.objects.all().iterator():
        first_pronoun_field = (
            CustomProfileField.objects.filter(
                realm=realm,
                field_type=PRONOUNS,
            )
            .order_by("order")
            .first()
        )

        if first_pronoun_field and not first_pronoun_field.display_in_profile_summary:
            first_pronoun_field.display_in_profile_summary = True
            first_pronoun_field.save(update_fields=["display_in_profile_summary"])
            print(
                f"Set display_in_profile_summary=True for first pronoun field "
                f"(id={first_pronoun_field.id}) in realm {realm.string_id}"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0806_stream_default_push_notifications"),
    ]

    operations = [
        migrations.RunPython(
            set_display_in_profile_summary_for_first_pronoun_field,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
