# Generated by Django 1.10.5 on 2017-03-21 15:56
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0064_sync_uploads_filesize_with_db'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='inline_image_preview',
            field=models.BooleanField(default=True),
        ),
    ]
