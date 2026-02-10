from django.db import migrations


class Migration(migrations.Migration):
    elidable = True

    dependencies = [
        ("analytics", "0017_regenerate_partial_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            "DELETE FROM analytics_usercount WHERE property = 'active_users_audit:is_bot:day'",
            elidable=True,
        )
    ]
