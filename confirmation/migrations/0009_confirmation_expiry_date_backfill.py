# Generated by Django 3.1.7 on 2021-03-31 20:47

import time
from datetime import timedelta

from django.conf import settings
from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_expiry_date_for_existing_confirmations(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Confirmation = apps.get_model("confirmation", "Confirmation")
    if not Confirmation.objects.exists():
        return

    # The values at the time of this migration
    INVITATION = 2
    UNSUBSCRIBE = 4
    MULTIUSE_INVITE = 6

    @transaction.atomic
    def backfill_confirmations_between(lower_bound: int, upper_bound: int) -> None:
        confirmations = Confirmation.objects.filter(id__gte=lower_bound, id__lte=upper_bound)
        for confirmation in confirmations:
            if confirmation.type in (INVITATION, MULTIUSE_INVITE):
                confirmation.expiry_date = confirmation.date_sent + timedelta(
                    days=settings.INVITATION_LINK_VALIDITY_DAYS
                )
            elif confirmation.type == UNSUBSCRIBE:
                # Unsubscribe links never expire, which we apparently implement as in 1M days.
                confirmation.expiry_date = confirmation.date_sent + timedelta(days=1000000)
            else:
                confirmation.expiry_date = confirmation.date_sent + timedelta(
                    days=settings.CONFIRMATION_LINK_DEFAULT_VALIDITY_DAYS
                )
        Confirmation.objects.bulk_update(confirmations, ["expiry_date"])

    # Because the ranges in this code are inclusive, subtracting 1 offers round numbers.
    BATCH_SIZE = 1000 - 1

    first_id = Confirmation.objects.earliest("id").id
    last_id = Confirmation.objects.latest("id").id

    id_range_lower_bound = first_id
    id_range_upper_bound = first_id + BATCH_SIZE
    while id_range_lower_bound <= last_id:
        print(f"Processed {id_range_lower_bound} / {last_id}")
        backfill_confirmations_between(id_range_lower_bound, id_range_upper_bound)
        id_range_lower_bound = id_range_upper_bound + 1
        id_range_upper_bound = id_range_lower_bound + BATCH_SIZE
        time.sleep(0.1)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("confirmation", "0008_confirmation_expiry_date"),
    ]

    operations = [
        migrations.RunPython(
            set_expiry_date_for_existing_confirmations,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
