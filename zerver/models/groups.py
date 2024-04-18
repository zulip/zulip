from django.db import models
from django.db.models import CASCADE
from django_cte import CTEManager

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


class UserGroup(models.Model):  # type: ignore[django-manager-missing] # django-stubs cannot resolve the custom CTEManager yet https://github.com/typeddjango/django-stubs/issues/1023
    objects: CTEManager = CTEManager()
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


class NamedUserGroup(UserGroup):  # type: ignore[django-manager-missing] # django-stubs cannot resolve the custom CTEManager yet https://github.com/typeddjango/django-stubs/issues/1023
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
    is_system_group = models.BooleanField(default=False, db_column="is_system_group")

    can_mention_group = models.ForeignKey(
        UserGroup, on_delete=models.RESTRICT, db_column="can_mention_group_id"
    )

    realm_for_sharding = models.ForeignKey("zerver.Realm", on_delete=CASCADE, db_column="realm_id")

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
        "can_mention_group": GroupPermissionSetting(
            require_system_group=False,
            allow_internet_group=False,
            allow_owners_group=False,
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=SystemGroups.EVERYONE,
            default_for_system_groups=SystemGroups.NOBODY,
            id_field_name="can_mention_group_id",
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
