from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0784_realmfilter_reverse_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmfilter",
            name="alternative_url_templates",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
