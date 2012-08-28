from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0529_fts_bigint_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="useractivityinterval",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="useractivity",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
