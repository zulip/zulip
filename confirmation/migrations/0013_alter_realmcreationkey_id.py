from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("confirmation", "0012_alter_confirmation_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realmcreationkey",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
