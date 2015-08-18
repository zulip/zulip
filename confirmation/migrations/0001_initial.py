# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Confirmation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('object_id', models.PositiveIntegerField()),
                ('date_sent', models.DateTimeField(verbose_name='sent')),
                ('confirmation_key', models.CharField(max_length=40, verbose_name='activation key')),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
                'verbose_name': 'confirmation email',
                'verbose_name_plural': 'confirmation emails',
            },
            bases=(models.Model,),
        ),
    ]
