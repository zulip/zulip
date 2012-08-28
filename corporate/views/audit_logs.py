from typing import Any

from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import render

from corporate.lib.activity import ActivityHeaderEntry, format_optional_datetime, make_table
from zerver.decorator import require_server_admin
from zerver.lib.typed_endpoint import PathOnly
from zerver.models.realm_audit_logs import AbstractRealmAuditLog, AuditLogEventType
from zilencer.models import RemoteRealmAuditLog, RemoteZulipServer, RemoteZulipServerAuditLog

USER_ROLES_KEY = "100: owner, 200: admin, 300: moderator, 400: member, 600: guest"


def get_remote_realm_host(audit_log: RemoteRealmAuditLog) -> str:
    if audit_log.remote_realm is None:
        # For pre-8.0 servers, we might only have the realm ID and thus
        # no RemoteRealm object yet, so we show that information instead.
        return f"N/A, realm ID: {audit_log.realm_id}"
    return audit_log.remote_realm.host


def get_human_role_count_data(audit_log: RemoteRealmAuditLog | RemoteZulipServerAuditLog) -> str:
    extra_data = audit_log.extra_data
    role_count = extra_data.get(AbstractRealmAuditLog.ROLE_COUNT, {})
    human_count_raw: dict[str, Any] = role_count.get(AbstractRealmAuditLog.ROLE_COUNT_HUMANS, {})
    if human_count_raw == {}:
        return "N/A"
    human_count_string = ""
    for role, count in human_count_raw.items():
        if int(count) > 0:
            human_count_string += f"{(role)}: {count}, "
    return human_count_string.strip(", ")


@require_server_admin
def get_remote_server_logs(request: HttpRequest, *, uuid: PathOnly[str]) -> HttpResponse:
    try:
        remote_server = RemoteZulipServer.objects.get(uuid=uuid)
    except RemoteZulipServer.DoesNotExist:
        return HttpResponseNotFound()

    remote_server_audit_logs = RemoteZulipServerAuditLog.objects.filter(
        server=remote_server
    ).order_by("-id")
    remote_realm_audit_logs = (
        RemoteRealmAuditLog.objects.filter(server=remote_server)
        .order_by("-id")
        .select_related("remote_realm")
    )

    title = f"{remote_server.hostname}"
    cols = [
        "Event time",
        "Event type",
        "Audit log ID",
        "Remote realm host",
        "Role count: human",
    ]

    def row(audit_log: RemoteRealmAuditLog | RemoteZulipServerAuditLog) -> list[Any]:
        return [
            audit_log.event_time,
            AuditLogEventType(audit_log.event_type).name,
            audit_log.id if isinstance(audit_log, RemoteRealmAuditLog) else f"S{audit_log.id}",
            get_remote_realm_host(audit_log) if isinstance(audit_log, RemoteRealmAuditLog) else "",
            get_human_role_count_data(audit_log)
            if audit_log.event_type in AbstractRealmAuditLog.SYNCED_BILLING_EVENTS
            else "",
        ]

    remote_server_audit_log_rows = list(map(row, remote_server_audit_logs))
    remote_realm_audit_log_rows = list(map(row, remote_realm_audit_logs))
    rows = remote_server_audit_log_rows + remote_realm_audit_log_rows

    header_entries = []
    if remote_server.last_version is not None:
        header_entries.append(
            ActivityHeaderEntry(
                name="Zulip version",
                value=remote_server.last_version,
            )
        )
    header_entries.append(
        ActivityHeaderEntry(
            name="Last audit log update",
            value=format_optional_datetime(remote_server.last_audit_log_update),
        )
    )
    header_entries.append(ActivityHeaderEntry(name="Role key", value=USER_ROLES_KEY))

    content = make_table(title, cols, rows, header=header_entries)

    return render(
        request,
        "corporate/activity/activity.html",
        context=dict(
            data=content,
            title=title,
            is_home=False,
        ),
    )
