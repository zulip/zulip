from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0783_realmfilter_example_input"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmfilter",
            name="reverse_template",
            field=models.TextField(blank=True, null=True),
        ),
    ]
