from django.db import migrations

REMOVED_COUNTS = (
    "active_users_log:is_bot:day",
    "active_users:is_bot:day",
)


class Migration(migrations.Migration):
    elidable = True

    dependencies = [
        ("analytics", "0018_remove_usercount_active_users_audit"),
    ]

    operations = [
        migrations.RunSQL(
            [
                ("DELETE FROM analytics_realmcount WHERE property IN %s", (REMOVED_COUNTS,)),
                (
                    "DELETE FROM analytics_installationcount WHERE property IN %s",
                    (REMOVED_COUNTS,),
                ),
            ],
            elidable=True,
        )
    ]
