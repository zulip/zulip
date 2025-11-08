from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0003_fillstate"),
    ]

    operations = [
        migrations.AddField(
            model_name="installationcount",
            name="subgroup",
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AddField(
            model_name="realmcount",
            name="subgroup",
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AddField(
            model_name="streamcount",
            name="subgroup",
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AddField(
            model_name="usercount",
            name="subgroup",
            field=models.CharField(max_length=16, null=True),
        ),
    ]
