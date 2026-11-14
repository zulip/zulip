from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def preserve_existing_subscription_colors(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Subscription = apps.get_model("zerver", "Subscription")
    Subscription.objects.filter(auto_color__isnull=True).update(auto_color=models.F("color"))


class Migration(migrations.Migration):
    dependencies = [("zerver", "0812_delete_inaccessible_user_topics")]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="default_color",
            field=models.CharField(default=None, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="color",
            field=models.CharField(default=None, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="auto_color",
            field=models.CharField(default=None, max_length=10, null=True),
        ),
        migrations.RunPython(preserve_existing_subscription_colors, migrations.RunPython.noop),
    ]
