from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("corporate", "0023_zulipsponsorshiprequest_customer"),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE corporate_zulipsponsorshiprequest
            SET customer_id = (
                SELECT id FROM corporate_customer WHERE corporate_customer.realm_id = corporate_zulipsponsorshiprequest.realm_id
            )
        """,
            elidable=True,
        ),
    ]
