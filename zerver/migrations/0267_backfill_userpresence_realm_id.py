from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0266_userpresence_realm"),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE zerver_userpresence
            SET realm_id = zerver_userprofile.realm_id
            FROM zerver_userprofile
            WHERE zerver_userprofile.id = zerver_userpresence.user_profile_id;
            """,
            reverse_sql="UPDATE zerver_userpresence SET realm_id = NULL",
            elidable=True,
        ),
    ]
