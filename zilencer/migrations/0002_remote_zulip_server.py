# -*- coding: utf-8 -*-
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zilencer', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RemotePushDeviceToken',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('user_id', models.BigIntegerField()),
                ('kind', models.PositiveSmallIntegerField(choices=[(1, 'apns'), (2, 'gcm')])),
                ('token', models.CharField(unique=True, max_length=4096)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('ios_app_id', models.TextField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='RemoteZulipServer',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('uuid', models.CharField(unique=True, max_length=36)),
                ('api_key', models.CharField(max_length=64)),
                ('hostname', models.CharField(unique=True, max_length=128)),
                ('contact_email', models.EmailField(max_length=254, blank=True)),
                ('last_updated', models.DateTimeField(verbose_name='last updated')),
            ],
        ),
        migrations.AddField(
            model_name='remotepushdevicetoken',
            name='server',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zilencer.RemoteZulipServer'),
        ),
    ]
