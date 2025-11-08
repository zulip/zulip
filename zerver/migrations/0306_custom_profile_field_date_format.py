from django.db import migrations


class Migration(migrations.Migration):
    """
    We previously accepted invalid ISO 8601 dates like 1909-3-5 for
    date values of custom profile fields. Correct them by adding the
    missing leading zeros: 1909-03-05.
    """

    dependencies = [
        ("zerver", "0305_realm_deactivated_redirect"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""\
                UPDATE zerver_customprofilefieldvalue
                SET value = to_char(to_date(value, 'YYYY-MM-DD'), 'YYYY-MM-DD')
                FROM zerver_customprofilefield AS f
                WHERE f.id = field_id
                AND f.field_type = 4
                AND CASE
                        WHEN f.field_type = 4
                        THEN value <> to_char(to_date(value, 'YYYY-MM-DD'), 'YYYY-MM-DD')
                    END;
            """,
            reverse_sql="",
            elidable=True,
        ),
    ]
