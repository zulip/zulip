# Generated by Django 1.11.6 on 2018-01-24 20:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0136_remove_userprofile_quota'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='upload_quota_gb',
            field=models.IntegerField(null=True),
        ),
    ]
