from django.db import migrations

# This matches analytics.lib.counts.LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
IGNORED = (
    "invites_sent::day",
    "mobile_pushes_sent::day",
    "active_users_log:is_bot:day",
    "active_users:is_bot:day",
)


class Migration(migrations.Migration):
    elidable = True

    dependencies = [
        (
            "zilencer",
            "0060_remove_remoterealmcount_unique_remote_realm_installation_count_and_more",
        ),
    ]

    operations = [
        migrations.RunSQL(
            [
                ("DELETE FROM zilencer_remoterealmcount WHERE property IN %s", (IGNORED,)),
                ("DELETE FROM zilencer_remoteinstallationcount WHERE property IN %s", (IGNORED,)),
            ],
            elidable=True,
        ),
    ]
