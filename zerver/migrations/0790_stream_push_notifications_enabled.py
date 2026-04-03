from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0789_add_external_auth_fields_to_preregistrationuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="push_notifications_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
