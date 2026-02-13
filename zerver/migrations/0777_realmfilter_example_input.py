from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmfilter",
            name="example_input",
            field=models.TextField(blank=True, null=True),
        ),
    ]
