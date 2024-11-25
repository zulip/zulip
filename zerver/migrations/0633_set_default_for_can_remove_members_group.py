# Generated by Django 5.0.9 on 2024-11-24 11:02

from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max, Min, OuterRef


def set_default_value_for_can_remove_members_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    BATCH_SIZE = 1000

    max_id = NamedUserGroup.objects.filter(can_remove_members_group=None).aggregate(Max("id"))[
        "id__max"
    ]
    if max_id is None:
        # Do nothing if there are no user groups on the server.
        return

    lower_bound = NamedUserGroup.objects.filter(can_remove_members_group=None).aggregate(Min("id"))[
        "id__min"
    ]

    while lower_bound <= max_id + BATCH_SIZE / 2:
        upper_bound = lower_bound + BATCH_SIZE - 1
        print(f"Processing batch {lower_bound} to {upper_bound} for NamedUserGroup")

        with transaction.atomic():
            # Users with permission to manage the group can remove members
            # from the group, so there is no need to give the permission
            # to any other user by default.
            NamedUserGroup.objects.filter(
                id__range=(lower_bound, upper_bound),
                can_remove_members_group=None,
            ).update(
                can_remove_members_group=NamedUserGroup.objects.filter(
                    name="role:nobody",
                    realm_for_sharding=OuterRef("realm_for_sharding"),
                    is_system_group=True,
                ).values("pk")
            )

        lower_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0632_namedusergroup_can_remove_members_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_remove_members_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
