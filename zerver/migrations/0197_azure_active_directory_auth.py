# Generated by Django 1.11.14 on 2018-10-11 00:12

import bitfield.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0196_add_realm_logo_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realm',
            name='authentication_methods',
            field=bitfield.models.BitField(['Google', 'Email', 'GitHub', 'LDAP', 'Dev', 'RemoteUser', 'AzureAD'], default=2147483647),
        ),
    ]
