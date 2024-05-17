import bitfield.models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0039_realmalias_drop_uniqueness"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="authentication_methods",
            field=bitfield.models.BitField(
                ["Google", "Email", "GitHub", "LDAP", "Dev", "RemoteUser"], default=2147483647
            ),
        ),
    ]
