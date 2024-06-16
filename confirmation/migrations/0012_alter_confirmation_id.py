from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("confirmation", "0011_alter_confirmation_expiry_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="confirmation",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
