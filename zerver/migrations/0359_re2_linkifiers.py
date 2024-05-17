import re2
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def delete_re2_invalid(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    options = re2.Options()
    options.log_errors = False

    RealmFilter = apps.get_model("zerver", "RealmFilter")
    found_errors = False
    for linkifier in RealmFilter.objects.all():
        try:
            re2.compile(linkifier.pattern, options=options)
        except re2.error:
            if not found_errors:
                print()
            found_errors = True
            print(
                f"Deleting linkifier {linkifier.id} in realm {linkifier.realm.string_id} which is not compatible with new re2 engine:"
            )
            print(f"  {linkifier.pattern} -> {linkifier.url_format_string}")
            linkifier.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0325_alter_realmplayground_unique_together"),
    ]

    operations = [
        migrations.RunPython(
            delete_re2_invalid,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
