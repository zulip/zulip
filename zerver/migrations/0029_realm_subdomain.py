from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_subdomain_of_default_realm(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    if settings.DEVELOPMENT:
        Realm = apps.get_model("zerver", "Realm")
        try:
            default_realm = Realm.objects.get(domain="zulip.com")
        except ObjectDoesNotExist:
            default_realm = None

        if default_realm is not None:
            default_realm.subdomain = "zulip"
            default_realm.save()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="subdomain",
            field=models.CharField(max_length=40, unique=True, null=True),
        ),
        migrations.RunPython(set_subdomain_of_default_realm, elidable=True),
    ]
