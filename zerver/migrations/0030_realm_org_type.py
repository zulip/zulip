from django.db import migrations, models

CORPORATE = 1


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0029_realm_subdomain"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="org_type",
            field=models.PositiveSmallIntegerField(default=CORPORATE),
        ),
    ]
