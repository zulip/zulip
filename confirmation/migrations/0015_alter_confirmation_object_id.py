from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("confirmation", "0014_confirmation_confirmatio_content_80155a_idx"),
        # We want to be linking to tables that are already bigints
        ("zerver", "0531_convert_most_ids_to_bigints"),
    ]

    operations = [
        migrations.AlterField(
            model_name="confirmation",
            name="object_id",
            field=models.PositiveBigIntegerField(db_index=True),
        ),
    ]
