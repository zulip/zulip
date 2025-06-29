from django.db import models
from django.db.models import CASCADE
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy

from zerver.lib.cache import cache_with_key, get_realm_system_groups_cache_key
from zerver.lib.types import GroupPermissionSetting
from zerver.models.users import UserProfile


class SystemGroups:
    FULL_MEMBERS = "role:fullmembers"
    EVERYONE_ON_INTERNET = "role:internet"
    OWNERS = "role:owners"
    ADMINISTRATORS = "role:administrators"
    MODERATORS = "role:moderators"
    MEMBERS = "role:members"
    EVERYONE = "role:everyone"
    NOBODY = "role:nobody"

    GROUP_DISPLAY_NAME_MAP = {
        NOBODY: gettext_lazy("Nobody"),
        OWNERS: gettext_lazy("Owners"),
        ADMINISTRATORS: gettext_lazy("Administrators"),
        MODERATORS: gettext_lazy("Moderators"),
        FULL_MEMBERS: gettext_lazy("Full members"),
        MEMBERS: gettext_lazy("Members"),
        EVERYONE: gettext_lazy("Everyone"),
        EVERYONE_ON_INTERNET: gettext_lazy("Everyone on the internet"),
    }


class UserGroup(models.Model):
    direct_members = models.ManyToManyField(
        UserProfile, through="zerver.UserGroupMembership", related_name="direct_groups"
    )
    direct_subgroups = models.ManyToManyField(
        "zerver.NamedUserGroup",
        symmetrical=False,
        through="zerver.GroupGroupMembership",
        through_fields=("supergroup", "subgroup"),
        related_name="direct_supergroups",
    )
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)


class NamedUserGroup(UserGroup):
    MAX_NAME_LENGTH = 100
    INVALID_NAME_PREFIXES = ["@", "role:", "user:", "stream:", "channel:"]

    # This field is automatically created by django, but we still need
    # to add this here to keep mypy happy when accessing usergroup_ptr.
    usergroup_ptr = models.OneToOneField(
        auto_created=True,
        on_delete=CASCADE,
        parent_link=True,
        primary_key=True,
        serialize=False,
        to=UserGroup,
        # We are not using the auto-generated name here to avoid
        # duplicate backward relation name because "can_mention_group"
        # setting also points to a UserGroup object.
        related_name="named_user_group",
    )
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_column="name")
    description = models.TextField(default="", db_column="description")
    date_created = models.DateTimeField(default=timezone_now, null=True)
    creator = models.ForeignKey(
        UserProfile, null=True, on_delete=models.SET_NULL, related_name="+", db_column="creator_id"
    )
    is_system_group = models.BooleanField(default=False, db_column="is_system_group")

    can_add_members_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )
    can_join_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT, related_name="+")
    can_leave_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT, related_name="+")
    can_manage_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT, related_name="+")
    can_mention_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, db_column="can_mention_group_id"
    )
    can_remove_members_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, related_name="+"
    )

    realm_for_sharding = models.ForeignKey("zerver.Realm", on_delete=CASCADE, db_column="realm_id")
    deactivated = models.BooleanField(default=False, db_default=False)

    # We do not have "Full members" and "Everyone on the internet"
    # group here since there isn't a separate role value for full
    # members and spectators.
    SYSTEM_USER_GROUP_ROLE_MAP = {
        UserProfile.ROLE_REALM_OWNER: {
            "name": SystemGroups.OWNERS,
            "description": "Owners of this organization",
        },
        UserProfile.ROLE_REALM_ADMINISTRATOR: {
            "name": SystemGroups.ADMINISTRATORS,
            "description": "Administrators of this organization, including owners",
        },
        UserProfile.ROLE_MODERATOR: {
            "name": SystemGroups.MODERATORS,
            "description": "Moderators of this organization, including administrators",
        },
        UserProfile.ROLE_MEMBER: {
            "name": SystemGroups.MEMBERS,
            "description": "Members of this organization, not including guests",
        },
        UserProfile.ROLE_GUEST: {
            "name": SystemGroups.EVERYONE,
            "description": "Everyone in this organization, including guests",
        },
    }

    GROUP_PERMISSION_SETTINGS = {
        "can_add_members_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name="group_creator",
            default_for_system_groups=SystemGroups.NOBODY,
        ),
        "can_join_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name=SystemGroups.NOBODY,
            default_for_system_groups=SystemGroups.NOBODY,
        ),
        "can_leave_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.EVERYONE,
            default_for_system_groups=SystemGroups.NOBODY,
        ),
        "can_manage_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name="group_creator",
            default_for_system_groups=SystemGroups.NOBODY,
        ),
        "can_mention_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.EVERYONE,
            default_for_system_groups=SystemGroups.NOBODY,
        ),
        "can_remove_members_group": GroupPermissionSetting(
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name=SystemGroups.NOBODY,
            default_for_system_groups=SystemGroups.NOBODY,
        ),
    }

    class Meta:
        unique_together = (("realm_for_sharding", "name"),)


class UserGroupMembership(models.Model):
    user_group = models.ForeignKey(UserGroup, on_delete=CASCADE, related_name="+")
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name="+")

    class Meta:
        unique_together = (("user_group", "user_profile"),)


class GroupGroupMembership(models.Model):
    supergroup = models.ForeignKey(UserGroup, on_delete=CASCADE, related_name="+")
    subgroup = models.ForeignKey(NamedUserGroup, on_delete=CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["supergroup", "subgroup"], name="zerver_groupgroupmembership_uniq"
            )
        ]


@cache_with_key(get_realm_system_groups_cache_key, timeout=3600 * 24 * 7)
def get_realm_system_groups_name_dict(realm_id: int) -> dict[int, str]:
    system_groups = NamedUserGroup.objects.filter(
        realm_id=realm_id, is_system_group=True
    ).values_list("id", "name")
    return dict(system_groups)
