# Generated by Django 5.0.5 on 2024-05-03 11:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0516_fix_confirmation_preregistrationusers"),
    ]

    operations = [
        migrations.AddField(
            model_name="customprofilefield",
            name="rendered_hint",
            field=models.TextField(default="", null=True),
        ),
        migrations.AddField(
            model_name="customprofilefield",
            name="rendered_name",
            field=models.TextField(default="", null=True),
        ),
    ]
