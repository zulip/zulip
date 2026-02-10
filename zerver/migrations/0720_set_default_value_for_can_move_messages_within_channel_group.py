from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max, Min, OuterRef


def set_default_value_for_can_move_messages_within_channel_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Stream = apps.get_model("zerver", "stream")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    BATCH_SIZE = 1000

    max_id = Stream.objects.filter(can_move_messages_within_channel_group=None).aggregate(
        Max("id")
    )["id__max"]
    if max_id is None:
        # Do nothing if there are no channels on the server.
        return

    lower_bound = Stream.objects.filter(can_move_messages_within_channel_group=None).aggregate(
        Min("id")
    )["id__min"]
    while lower_bound <= max_id + BATCH_SIZE / 2:
        upper_bound = lower_bound + BATCH_SIZE - 1
        print(f"Processing batch {lower_bound} to {upper_bound} for Stream")

        with transaction.atomic():
            Stream.objects.filter(
                id__range=(lower_bound, upper_bound),
                can_move_messages_within_channel_group=None,
            ).update(
                can_move_messages_within_channel_group=NamedUserGroup.objects.filter(
                    name="role:nobody",
                    realm_for_sharding=OuterRef("realm_id"),
                    is_system_group=True,
                ).values("pk")
            )

        lower_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0719_stream_can_move_messages_within_channel_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_move_messages_within_channel_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
