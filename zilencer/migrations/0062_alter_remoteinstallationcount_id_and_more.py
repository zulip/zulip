from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zilencer", "0061_clean_count_tables"),
    ]

    operations = [
        migrations.AlterField(
            model_name="remoteinstallationcount",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="remoterealmcount",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
