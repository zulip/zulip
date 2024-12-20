# Generated by Django 3.2.13 on 2022-06-28 17:36

from django.conf import settings
from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

# This migration is a copy of
# zerver/migrations/0382_create_role_based_system_groups.py" run
# for the internal realm only.


def create_role_based_system_groups_for_internal_realms(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")
    UserGroup = apps.get_model("zerver", "UserGroup")
    GroupGroupMembership = apps.get_model("zerver", "GroupGroupMembership")
    UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")

    UserProfile.ROLE_REALM_OWNER = 100
    UserProfile.ROLE_REALM_ADMINISTRATOR = 200
    UserProfile.ROLE_MODERATOR = 300
    UserProfile.ROLE_MEMBER = 400
    UserProfile.ROLE_GUEST = 600

    try:
        realm = Realm.objects.get(string_id=settings.SYSTEM_BOT_REALM)
    except Realm.DoesNotExist:
        # Server not initialized, or no system bot realm. Either way,
        # we shouldn't do anything.
        return

    SYSTEM_USER_GROUP_ROLE_MAP = {
        UserProfile.ROLE_REALM_OWNER: {
            "name": "@role:owners",
            "description": "Owners of this organization",
        },
        UserProfile.ROLE_REALM_ADMINISTRATOR: {
            "name": "@role:administrators",
            "description": "Administrators of this organization, including owners",
        },
        UserProfile.ROLE_MODERATOR: {
            "name": "@role:moderators",
            "description": "Moderators of this organization, including administrators",
        },
        UserProfile.ROLE_MEMBER: {
            "name": "@role:members",
            "description": "Members of this organization, not including guests",
        },
        UserProfile.ROLE_GUEST: {
            "name": "@role:everyone",
            "description": "Everyone in this organization, including guests",
        },
    }

    with transaction.atomic():
        if UserGroup.objects.filter(
            realm=realm, name="@role:internet", is_system_group=True
        ).exists():
            # Handle the case where we are rerunning after a
            # failure, and had already created groups.
            return

        role_system_groups_dict = {
            role: UserGroup(
                name=user_group_params["name"],
                description=user_group_params["description"],
                realm=realm,
                is_system_group=True,
            )
            for role, user_group_params in SYSTEM_USER_GROUP_ROLE_MAP.items()
        }

        full_members_system_group = UserGroup(
            name="@role:fullmembers",
            description="Members of this organization, not including new accounts and guests",
            realm=realm,
            is_system_group=True,
        )
        everyone_on_internet_system_group = UserGroup(
            name="@role:internet",
            description="Everyone on the Internet",
            realm=realm,
            is_system_group=True,
        )

        system_user_groups_list = [
            role_system_groups_dict[UserProfile.ROLE_REALM_OWNER],
            role_system_groups_dict[UserProfile.ROLE_REALM_ADMINISTRATOR],
            role_system_groups_dict[UserProfile.ROLE_MODERATOR],
            full_members_system_group,
            role_system_groups_dict[UserProfile.ROLE_MEMBER],
            role_system_groups_dict[UserProfile.ROLE_GUEST],
            everyone_on_internet_system_group,
        ]

        UserGroup.objects.bulk_create(system_user_groups_list)

        subgroup_objects = []
        subgroup, remaining_groups = system_user_groups_list[0], system_user_groups_list[1:]
        for supergroup in remaining_groups:
            subgroup_objects.append(GroupGroupMembership(subgroup=subgroup, supergroup=supergroup))
            subgroup = supergroup

        GroupGroupMembership.objects.bulk_create(subgroup_objects)

        users = UserProfile.objects.filter(realm=realm).only("id", "role", "date_joined")
        group_membership_objects = []
        for user in users:
            system_group = role_system_groups_dict[user.role]
            group_membership_objects.append(
                UserGroupMembership(user_profile=user, user_group=system_group)
            )

            if (
                user.role == UserProfile.ROLE_MEMBER
                and (timezone_now() - user.date_joined).days >= realm.waiting_period_threshold
            ):
                group_membership_objects.append(
                    UserGroupMembership(user_profile=user, user_group=full_members_system_group)
                )

        UserGroupMembership.objects.bulk_create(group_membership_objects)


def delete_role_based_system_groups_for_internal_realms(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    UserGroup = apps.get_model("zerver", "UserGroup")
    GroupGroupMembership = apps.get_model("zerver", "GroupGroupMembership")
    UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")
    Realm = apps.get_model("zerver", "Realm")

    try:
        realm = Realm.objects.get(string_id=settings.SYSTEM_BOT_REALM)
    except Realm.DoesNotExist:
        # Server not initialized, or no system bot realm. Either way, we shouldn't do anything.
        return

    with transaction.atomic():
        GroupGroupMembership.objects.filter(subgroup__realm=realm).delete()
        UserGroupMembership.objects.filter(
            user_group__realm=realm, user_group__is_system_group=True
        ).delete()
        UserGroup.objects.filter(realm=realm, is_system_group=True).delete()


class Migration(migrations.Migration):
    """This migration is a copy of
    "zerver/migrations/0402_alter_usertopic_visibility_policy.py" run
    for the internal realm only.
    """

    dependencies = [
        ("zerver", "0402_alter_usertopic_visibility_policy"),
    ]

    operations = [
        migrations.RunPython(
            create_role_based_system_groups_for_internal_realms,
            reverse_code=delete_role_based_system_groups_for_internal_realms,
            elidable=True,
        ),
    ]
