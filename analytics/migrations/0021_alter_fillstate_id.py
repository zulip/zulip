from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0020_alter_installationcount_id_alter_realmcount_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fillstate",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
