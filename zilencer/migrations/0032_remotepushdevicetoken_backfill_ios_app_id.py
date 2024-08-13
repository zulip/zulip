from django.db import migrations


class Migration(migrations.Migration):
    """
    Previous versions of zilencer dropped the ios_app_id on the floor
    when registering a push token, and then effectively assumed
    the value was "org.zulip.Zulip".

    We're going to start actually using that parameter.  To preserve
    the existing behavior for existing tokens, backfill the value.
    """

    dependencies = [
        ("zilencer", "0031_alter_remoteinstallationcount_remote_id_and_more"),
    ]

    FORMERLY_IMPLICIT_IOS_APP_ID = "org.zulip.Zulip"

    operations = [
        migrations.RunSQL(
            sql=[
                (
                    """
            UPDATE zilencer_remotepushdevicetoken
            SET ios_app_id = %s
            WHERE kind = 1 AND ios_app_id IS NULL
            """,
                    [FORMERLY_IMPLICIT_IOS_APP_ID],
                )
            ],
            # The updated table is still valid with the old schema;
            # so to reverse, a no-op suffices.
            reverse_sql=[],
            elidable=True,
        ),
    ]
