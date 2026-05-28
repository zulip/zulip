from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0787_alter_realm_workplace_users_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmfilter",
            name="alternative_url_templates",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
