# Generated by Django 1.11.2 on 2017-07-08 04:23
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('confirmation', '0003_emailchangeconfirmation'),
    ]

    operations = [
        migrations.DeleteModel(
            name='EmailChangeConfirmation',
        ),
        migrations.AlterModelOptions(
            name='confirmation',
            options={},
        ),
        migrations.AddField(
            model_name='confirmation',
            name='type',
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='confirmation',
            name='confirmation_key',
            field=models.CharField(max_length=40),
        ),
        migrations.AlterField(
            model_name='confirmation',
            name='date_sent',
            field=models.DateTimeField(),
        ),
    ]
