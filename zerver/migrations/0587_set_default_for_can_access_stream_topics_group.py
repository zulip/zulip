from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max, Min, OuterRef, Subquery


def set_default_value_for_can_access_stream_topics_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Stream = apps.get_model("zerver", "Stream")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    BATCH_SIZE = 1000
    max_id = Stream.objects.filter(can_access_stream_topics_group=None).aggregate(Max("id"))[
        "id__max"
    ]

    if max_id is None:
        # Do nothing if there are no Stream object on the server.
        return

    lower_bound = Stream.objects.filter(can_access_stream_topics_group=None).aggregate(Min("id"))[
        "id__min"
    ]
    while lower_bound <= max_id:
        upper_bound = lower_bound + BATCH_SIZE - 1
        print(f"Processing batch {lower_bound} to {upper_bound} for Stream")

        with transaction.atomic():
            subquery = NamedUserGroup.objects.filter(
                name="role:everyone", realm=OuterRef("realm"), is_system_group=True
            ).values("id")[:1]

            Stream.objects.filter(
                id__range=(lower_bound, upper_bound), can_access_stream_topics_group=None
            ).update(can_access_stream_topics_group=Subquery(subquery))

        lower_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0586_stream_can_access_stream_topics_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_access_stream_topics_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
