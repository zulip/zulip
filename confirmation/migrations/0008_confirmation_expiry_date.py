from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("confirmation", "0007_add_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="confirmation",
            name="expiry_date",
            field=models.DateTimeField(db_index=True, null=True),
            preserve_default=False,
        ),
    ]
