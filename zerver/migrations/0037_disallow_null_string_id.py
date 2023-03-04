from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.utils import IntegrityError


def set_string_id_using_domain(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    for realm in Realm.objects.all():
        if not realm.string_id:
            prefix = realm.domain.split(".")[0]
            try:
                realm.string_id = prefix
                realm.save(update_fields=["string_id"])
                continue
            except IntegrityError:
                pass
            for i in range(1, 100):
                try:
                    realm.string_id = prefix + str(i)
                    realm.save(update_fields=["string_id"])
                    continue
                except IntegrityError:
                    pass
            raise RuntimeError(f"Unable to find a good string_id for realm {realm}")


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0036_rename_subdomain_to_string_id"),
    ]

    operations = [
        migrations.RunPython(set_string_id_using_domain, elidable=True),
        migrations.AlterField(
            model_name="realm",
            name="string_id",
            field=models.CharField(unique=True, max_length=40),
        ),
    ]
