from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0562_remove_realm_create_web_public_stream_policy"),
    ]

    operations = [
        migrations.RunSQL(
            "UPDATE zerver_realm SET delete_own_message_policy = 1 where string_id = 'zulipinternal'",
            elidable=True,
        )
    ]
