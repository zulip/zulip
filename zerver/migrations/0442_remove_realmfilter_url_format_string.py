from django.db import migrations, models

from zerver.models import url_template_validator


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0441_backfill_realmfilter_url_template"),
    ]

    operations = [
        migrations.RemoveField(model_name="realmfilter", name="url_format_string"),
        migrations.AlterField(
            model_name="realmfilter",
            name="url_template",
            field=models.TextField(validators=[url_template_validator], null=False),
        ),
    ]
