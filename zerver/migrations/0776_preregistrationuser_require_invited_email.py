from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0775_customprofilefield_use_for_user_matching"),
    ]

    operations = [
        migrations.AddField(
            model_name="preregistrationuser",
            name="require_invited_email",
            field=models.BooleanField(default=False),
        ),
    ]
