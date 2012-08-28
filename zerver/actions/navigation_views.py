from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.navigation_views import get_navigation_view_dict
from zerver.models import NavigationView, RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_add_navigation_view(
    user: UserProfile,
    fragment: str,
    is_pinned: bool,
    name: str | None = None,
) -> NavigationView:
    navigation_view = NavigationView.objects.create(
        user=user,
        fragment=fragment,
        is_pinned=is_pinned,
        name=name,
    )

    RealmAuditLog.objects.create(
        realm=user.realm,
        acting_user=user,
        modified_user=user,
        event_type=AuditLogEventType.NAVIGATION_VIEW_CREATED,
        event_time=timezone_now(),
        extra_data={"fragment": fragment},
    )

    event = {
        "type": "navigation_view",
        "op": "add",
        "navigation_view": get_navigation_view_dict(navigation_view),
    }
    send_event_on_commit(user.realm, event, [user.id])
    return navigation_view


@transaction.atomic(durable=True)
def do_update_navigation_view(
    user: UserProfile,
    navigation_view: NavigationView,
    is_pinned: bool | None,
    name: str | None = None,
) -> None:
    update_dict: dict[str, str | bool] = {}
    audit_logs_extra_data: list[dict[str, str | bool | None]] = []
    if name is not None:
        old_name = navigation_view.name
        navigation_view.name = name
        update_dict["name"] = name
        audit_logs_extra_data.append(
            {
                "fragment": navigation_view.fragment,
                RealmAuditLog.OLD_VALUE: old_name,
                RealmAuditLog.NEW_VALUE: name,
                "property": "name",
            }
        )

    if is_pinned is not None:
        old_is_pinned_value = navigation_view.is_pinned
        navigation_view.is_pinned = is_pinned
        update_dict["is_pinned"] = is_pinned
        audit_logs_extra_data.append(
            {
                "fragment": navigation_view.fragment,
                RealmAuditLog.OLD_VALUE: old_is_pinned_value,
                RealmAuditLog.NEW_VALUE: is_pinned,
                "property": "is_pinned",
            }
        )

    navigation_view.save(update_fields=["name", "is_pinned"])

    now = timezone_now()
    for audit_log_extra_data in audit_logs_extra_data:
        RealmAuditLog.objects.create(
            realm=user.realm,
            acting_user=user,
            modified_user=user,
            event_type=AuditLogEventType.NAVIGATION_VIEW_UPDATED,
            event_time=now,
            extra_data=audit_log_extra_data,
        )

    event = {
        "type": "navigation_view",
        "op": "update",
        "fragment": navigation_view.fragment,
        "data": update_dict,
    }
    send_event_on_commit(user.realm, event, [user.id])


@transaction.atomic(durable=True)
def do_remove_navigation_view(
    user: UserProfile,
    navigation_view: NavigationView,
) -> None:
    fragment = navigation_view.fragment
    navigation_view.delete()

    RealmAuditLog.objects.create(
        realm=user.realm,
        acting_user=user,
        modified_user=user,
        event_type=AuditLogEventType.NAVIGATION_VIEW_DELETED,
        event_time=timezone_now(),
        extra_data={"fragment": fragment},
    )

    event = {
        "type": "navigation_view",
        "op": "remove",
        "fragment": navigation_view.fragment,
    }
    send_event_on_commit(user.realm, event, [user.id])
