from collections import defaultdict

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, F, OuterRef, Q
from django_cte import CTE, with_cte

ROLE_GUEST = 600  # UserProfile.ROLE_GUEST
BATCH_SIZE = 1000


def delete_inaccessible_user_topics(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Removes UserTopic rows whose owner no longer has content access to
    the channel the row points at.

    Before the accompanying fix, moving a topic to a channel a user could
    not access left that user's topic visibility policy (mute/follow)
    behind, so UserTopic rows pointing at channels the user cannot access
    can exist in the database.
    """
    Realm = apps.get_model("zerver", "Realm")
    UserTopic = apps.get_model("zerver", "UserTopic")
    Subscription = apps.get_model("zerver", "Subscription")
    UserGroup = apps.get_model("zerver", "UserGroup")
    UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")
    GroupGroupMembership = apps.get_model("zerver", "GroupGroupMembership")

    # These need no group lookup, so filter them out first; only the remainder
    # require the (more expensive) recursive-group-membership check below.
    has_content_access_without_group_check = (
        Q(stream__is_web_public=True)
        | Exists(
            Subscription.objects.filter(
                recipient_id=OuterRef("recipient_id"),
                user_profile_id=OuterRef("user_profile_id"),
                active=True,
            )
        )
        | (Q(stream__invite_only=False) & ~Q(user_profile__role=ROLE_GUEST))
    )

    def get_recursive_group_ids_by_user(user_ids: set[int]) -> dict[int, set[int]]:
        """Maps each user to every group they belong to, directly or
        transitively through subgroup relationships.

        This duplicates get_user_id_annotated_recursive_membership_groups_for_users
        from zerver.lib.user_groups.
        """
        recursive_group_ids_by_user: dict[int, set[int]] = defaultdict(set)
        if len(user_ids) == 0:
            return recursive_group_ids_by_user

        cte = CTE.recursive(
            lambda cte: (
                UserGroupMembership.objects.filter(user_profile_id__in=user_ids)
                .values(group_id=F("user_group_id"), user_id=F("user_profile_id"))
                .union(
                    cte.join(GroupGroupMembership, subgroup_id=cte.col.group_id).values(
                        group_id=F("supergroup_id"), user_id=cte.col.user_id
                    )
                )
            )
        )
        memberships = with_cte(cte, select=cte.join(UserGroup, id=cte.col.group_id)).annotate(
            user_id=cte.col.user_id
        )
        for group_id, user_id in memberships.values_list("id", "user_id"):
            recursive_group_ids_by_user[user_id].add(group_id)
        return recursive_group_ids_by_user

    def user_topic_ids_in_inaccessible_channels(
        candidate_batch: list[dict[str, int]],
    ) -> list[int]:
        # For these rows, the only remaining way the user has access is
        # recursive membership in the channel's can_subscribe_group or
        # can_add_subscribers_group. Guests never gain access that way
        # (those settings disallow the everyone group), so only
        # non-guests need the check.
        non_guest_user_ids = {
            row["user_profile_id"]
            for row in candidate_batch
            if row["user_profile__role"] != ROLE_GUEST
        }
        recursive_group_ids_by_user = get_recursive_group_ids_by_user(non_guest_user_ids)

        ids_to_delete = []
        for row in candidate_batch:
            if row["user_profile__role"] == ROLE_GUEST:
                ids_to_delete.append(row["id"])
                continue
            user_group_ids = recursive_group_ids_by_user.get(row["user_profile_id"], set())
            user_has_content_access = (
                row["stream__can_subscribe_group_id"] in user_group_ids
                or row["stream__can_add_subscribers_group_id"] in user_group_ids
            )
            if not user_has_content_access:
                ids_to_delete.append(row["id"])
        return ids_to_delete

    total_deleted = 0
    for realm_id in Realm.objects.order_by("id").values_list("id", flat=True).iterator():
        candidate_ids = list(
            UserTopic.objects.filter(stream__realm_id=realm_id)
            .exclude(has_content_access_without_group_check)
            .values_list("id", flat=True)
        )
        if len(candidate_ids) == 0:
            continue

        # Determining which rows point at inaccessible channels needs the
        # recursive-group membership query, so do it in fixed-size batches
        # to keep that query (and its results) bounded even within one realm.
        rows_deleted_in_realm = 0
        total_candidates = len(candidate_ids)
        for chunk_start in range(0, total_candidates, BATCH_SIZE):
            batch_ids = candidate_ids[chunk_start : chunk_start + BATCH_SIZE]
            candidate_batch = list(
                UserTopic.objects.filter(id__in=batch_ids).values(
                    "id",
                    "user_profile_id",
                    "user_profile__role",
                    "stream__can_subscribe_group_id",
                    "stream__can_add_subscribers_group_id",
                )
            )
            ids_to_delete = user_topic_ids_in_inaccessible_channels(candidate_batch)

            if len(ids_to_delete) > 0:
                UserTopic.objects.filter(id__in=ids_to_delete).delete()
                rows_deleted_in_realm += len(ids_to_delete)

            processed = min(chunk_start + BATCH_SIZE, total_candidates)
            print(
                f"Realm {realm_id}: processed {processed}/{total_candidates} "
                f"candidate UserTopic rows, deleted {rows_deleted_in_realm}."
            )
        total_deleted += rows_deleted_in_realm

    if total_deleted > 0:
        print(f"Deleted {total_deleted} inaccessible UserTopic rows in total.")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0811_usermessage_add_hide_link_previews"),
    ]

    operations = [
        migrations.RunPython(
            delete_inaccessible_user_topics,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
