from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0782_delete_unused_anonymous_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmfilter",
            name="example_input",
            field=models.TextField(blank=True, null=True),
        ),
    ]
