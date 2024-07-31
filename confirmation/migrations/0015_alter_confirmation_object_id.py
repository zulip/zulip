from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("confirmation", "0014_confirmation_confirmatio_content_80155a_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="confirmation",
            name="object_id",
            field=models.PositiveBigIntegerField(db_index=True),
        ),
    ]
