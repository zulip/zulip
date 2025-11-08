from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from corporate.lib.activity import ActivityHeaderEntry, format_optional_datetime, make_table
from corporate.models.customers import Customer
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan
from zerver.decorator import require_server_admin


def get_plan_billing_entity_name(customer: Customer) -> str:
    if customer.realm:
        return customer.realm.name
    elif customer.remote_realm:
        return customer.remote_realm.name
    assert customer.remote_server is not None
    return customer.remote_server.hostname


@require_server_admin
def get_plan_ledger(request: HttpRequest, plan_id: int) -> HttpResponse:
    plan = CustomerPlan.objects.get(id=plan_id)
    ledger_entries = LicenseLedger.objects.filter(plan=plan).order_by("-event_time")

    name = get_plan_billing_entity_name(plan.customer)
    title = f"{name}"
    cols = [
        "Event time (UTC)",
        "Renewal",
        "License count",
        "Renewal count",
    ]

    def row(record: LicenseLedger) -> list[Any]:
        return [
            format_optional_datetime(record.event_time),
            record.is_renewal,
            record.licenses,
            record.licenses_at_next_renewal,
        ]

    rows = list(map(row, ledger_entries))

    header_entries = []
    header_entries.append(
        ActivityHeaderEntry(name="Plan name", value=CustomerPlan.name_from_tier(plan.tier))
    )
    header_entries.append(
        ActivityHeaderEntry(
            name="Start of next billing cycle (UTC)",
            value=format_optional_datetime(plan.next_invoice_date, True),
        )
    )
    if plan.invoiced_through is not None:
        header_entries.append(
            ActivityHeaderEntry(
                name="Entry last checked during invoicing",
                value=str(plan.invoiced_through),
            )
        )

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
