from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0775_customprofilefield_use_for_user_matching"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmfilter",
            name="example_input",
            field=models.TextField(blank=True, null=True),
        ),
    ]
