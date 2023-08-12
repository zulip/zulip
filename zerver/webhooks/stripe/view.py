# Webhooks for external integrations.
import time
from typing import Dict, Optional, Sequence, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


class SuppressedEventError(Exception):
    pass


class NotImplementedEventTypeError(SuppressedEventError):
    pass


ALL_EVENT_TYPES = [
    "charge.dispute.closed",
    "charge.dispute.created",
    "charge.failed",
    "charge.succeeded",
    "charge.succeeded",
    "customer.created",
    "customer.created",
    "customer.deleted",
    "customer.discount.created",
    "customer.subscription.created",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
    "customer.subscription.updated",
    "customer.updated",
    "invoice.created",
    "invoice.updated",
    "invoice.payment_failed",
    "invoiceitem.created",
    "charge.refund.updated",
    "charge.refund.updated",
]


@webhook_view("Stripe", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_stripe_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
    stream: str = "test",
) -> HttpResponse:
    try:
        topic, body = topic_and_body(payload)
    except SuppressedEventError:  # nocoverage
        return json_success(request)
    check_send_webhook_message(
        request, user_profile, topic, body, payload["type"].tame(check_string)
    )
    return json_success(request)


def topic_and_body(payload: WildValue) -> Tuple[str, str]:
    event_type = payload["type"].tame(
        check_string
    )  # invoice.created, customer.subscription.created, etc
    if len(event_type.split(".")) == 3:
        category, resource, event = event_type.split(".")
    else:
        resource, event = event_type.split(".")
        category = resource

    object_ = payload["data"]["object"]  # The full, updated Stripe object

    # Set the topic to the customer_id when we can
    topic = ""
    customer_id = object_.get("customer").tame(check_none_or(check_string))
    if customer_id is not None:
        # Running into the 60 character topic limit.
        # topic = '[{}](https://dashboard.stripe.com/customers/{})' % (customer_id, customer_id)
        topic = customer_id
    body = None

    def update_string(blacklist: Sequence[str] = []) -> str:
        assert "previous_attributes" in payload["data"]
        previous_attributes = set(payload["data"]["previous_attributes"].keys()).difference(
            blacklist
        )
        if not previous_attributes:  # nocoverage
            raise SuppressedEventError
        return "".join(
            "\n* "
            + attribute.replace("_", " ").capitalize()
            + " is now "
            + stringify(object_[attribute].value)
            for attribute in sorted(previous_attributes)
        )

    def default_body(update_blacklist: Sequence[str] = []) -> str:
        body = "{resource} {verbed}".format(
            resource=linkified_id(object_["id"].tame(check_string)), verbed=event.replace("_", " ")
        )
        if event == "updated":
            return body + update_string(blacklist=update_blacklist)
        return body

    if category == "account":  # nocoverage
        if resource == "account":
            if event == "updated":
                if "previous_attributes" not in payload["data"]:
                    raise SuppressedEventError
                topic = "account updates"
                body = update_string()
        else:
            # Part of Stripe Connect
            raise NotImplementedEventTypeError
    if category == "application_fee":  # nocoverage
        # Part of Stripe Connect
        raise NotImplementedEventTypeError
    if category == "balance":  # nocoverage
        # Not that interesting to most businesses, I think
        raise NotImplementedEventTypeError
    if category == "charge":
        if resource == "charge":
            if not topic:  # only in legacy fixtures
                topic = "charges"
            body = "{resource} for {amount} {verbed}".format(
                resource=linkified_id(object_["id"].tame(check_string)),
                amount=amount_string(
                    object_["amount"].tame(check_int), object_["currency"].tame(check_string)
                ),
                verbed=event,
            )
            if object_["failure_code"]:  # nocoverage
                body += ". Failure code: {}".format(object_["failure_code"].tame(check_string))
        if resource == "dispute":
            topic = "disputes"
            body = default_body() + ". Current status: {status}.".format(
                status=object_["status"].tame(check_string).replace("_", " ")
            )
        if resource == "refund":
            topic = "refunds"
            body = "A {resource} for a {charge} of {amount} was updated.".format(
                resource=linkified_id(object_["id"].tame(check_string), lower=True),
                charge=linkified_id(object_["charge"].tame(check_string), lower=True),
                amount=amount_string(
                    object_["amount"].tame(check_int), object_["currency"].tame(check_string)
                ),
            )
    if category == "checkout_beta":  # nocoverage
        # Not sure what this is
        raise NotImplementedEventTypeError
    if category == "coupon":  # nocoverage
        # Not something that likely happens programmatically
        raise NotImplementedEventTypeError
    if category == "customer":
        if resource == "customer":
            # Running into the 60 character topic limit.
            # topic = '[{}](https://dashboard.stripe.com/customers/{})' % (object_['id'], object_['id'])
            topic = object_["id"].tame(check_string)
            body = default_body(update_blacklist=["delinquent", "currency", "default_source"])
            if event == "created":
                if object_["email"]:
                    body += "\nEmail: {}".format(object_["email"].tame(check_string))
                if object_["metadata"]:  # nocoverage
                    for key, value in object_["metadata"].items():
                        body += f"\n{key}: {value.tame(check_string)}"
        if resource == "discount":
            body = "Discount {verbed} ([{coupon_name}]({coupon_url})).".format(
                verbed=event.replace("_", " "),
                coupon_name=object_["coupon"]["name"].tame(check_string),
                coupon_url="https://dashboard.stripe.com/{}/{}".format(
                    "coupons", object_["coupon"]["id"].tame(check_string)
                ),
            )
        if resource == "source":  # nocoverage
            body = default_body()
        if resource == "subscription":
            body = default_body()
            if event == "trial_will_end":
                DAY = 60 * 60 * 24  # seconds in a day
                # Basically always three: https://stripe.com/docs/api/python#event_types
                body += " in {days} days".format(
                    days=int((object_["trial_end"].tame(check_int) - time.time() + DAY // 2) // DAY)
                )
            if event == "created":
                if object_["plan"]:
                    nickname = object_["plan"]["nickname"].tame(check_none_or(check_string))
                    if nickname is not None:
                        body += "\nPlan: [{plan_nickname}](https://dashboard.stripe.com/plans/{plan_id})".format(
                            plan_nickname=object_["plan"]["nickname"].tame(check_string),
                            plan_id=object_["plan"]["id"].tame(check_string),
                        )
                    else:
                        body += "\nPlan: https://dashboard.stripe.com/plans/{plan_id}".format(
                            plan_id=object_["plan"]["id"].tame(check_string),
                        )
                if object_["quantity"]:
                    body += "\nQuantity: {}".format(object_["quantity"].tame(check_int))
                if "billing" in object_:  # nocoverage
                    body += "\nBilling method: {}".format(
                        object_["billing"].tame(check_string).replace("_", " ")
                    )
    if category == "file":  # nocoverage
        topic = "files"
        body = default_body() + " ({purpose}). \nTitle: {title}".format(
            purpose=object_["purpose"].tame(check_string).replace("_", " "),
            title=object_["title"].tame(check_string),
        )
    if category == "invoice":
        if event == "upcoming":  # nocoverage
            body = "Upcoming invoice created"
        elif (
            event == "updated"
            and payload["data"]["previous_attributes"].get("paid").tame(check_none_or(check_bool))
            is False
            and object_["paid"].tame(check_bool) is True
            and object_["amount_paid"].tame(check_int) != 0
            and object_["amount_remaining"].tame(check_int) == 0
        ):
            # We are taking advantage of logical AND short circuiting here since we need the else
            # statement below.
            object_id = object_["id"].tame(check_string)
            invoice_link = f"https://dashboard.stripe.com/invoices/{object_id}"
            body = f"[Invoice]({invoice_link}) is now paid"
        else:
            body = default_body(
                update_blacklist=[
                    "lines",
                    "description",
                    "number",
                    "finalized_at",
                    "status_transitions",
                    "payment_intent",
                ]
            )
        if event == "created":
            # Could potentially add link to invoice PDF here
            body += " ({reason})\nTotal: {total}\nAmount due: {due}".format(
                reason=object_["billing_reason"].tame(check_string).replace("_", " "),
                total=amount_string(
                    object_["total"].tame(check_int), object_["currency"].tame(check_string)
                ),
                due=amount_string(
                    object_["amount_due"].tame(check_int), object_["currency"].tame(check_string)
                ),
            )
    if category == "invoiceitem":
        body = default_body(update_blacklist=["description", "invoice"])
        if event == "created":
            body += " for {amount}".format(
                amount=amount_string(
                    object_["amount"].tame(check_int), object_["currency"].tame(check_string)
                )
            )
    if category.startswith("issuing"):  # nocoverage
        # Not implemented
        raise NotImplementedEventTypeError
    if category.startswith("order"):  # nocoverage
        # Not implemented
        raise NotImplementedEventTypeError
    if category in [
        "payment_intent",
        "payout",
        "plan",
        "product",
        "recipient",
        "reporting",
        "review",
        "sigma",
        "sku",
        "source",
        "subscription_schedule",
        "topup",
        "transfer",
    ]:  # nocoverage
        # Not implemented. In theory doing something like
        #   body = default_body()
        # may not be hard for some of these
        raise NotImplementedEventTypeError

    if body is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    return (topic, body)


def amount_string(amount: int, currency: str) -> str:
    zero_decimal_currencies = [
        "bif",
        "djf",
        "jpy",
        "krw",
        "pyg",
        "vnd",
        "xaf",
        "xpf",
        "clp",
        "gnf",
        "kmf",
        "mga",
        "rwf",
        "vuv",
        "xof",
    ]
    if currency in zero_decimal_currencies:
        decimal_amount = str(amount)  # nocoverage
    else:
        decimal_amount = f"{float(amount) * 0.01:.02f}"

    if currency == "usd":  # nocoverage
        return "$" + decimal_amount
    return decimal_amount + f" {currency.upper()}"


def linkified_id(object_id: str, lower: bool = False) -> str:
    names_and_urls: Dict[str, Tuple[str, Optional[str]]] = {
        # Core resources
        "ch": ("Charge", "charges"),
        "cus": ("Customer", "customers"),
        "dp": ("Dispute", "disputes"),
        "du": ("Dispute", "disputes"),
        "file": ("File", "files"),
        "link": ("File link", "file_links"),
        "pi": ("Payment intent", "payment_intents"),
        "po": ("Payout", "payouts"),
        "prod": ("Product", "products"),
        "re": ("Refund", "refunds"),
        "tok": ("Token", "tokens"),
        # Payment methods
        # payment methods have URL prefixes like /customers/cus_id/sources
        "ba": ("Bank account", None),
        "card": ("Card", None),
        "src": ("Source", None),
        # Billing
        # coupons have a configurable id, but the URL prefix is /coupons
        # discounts don't have a URL, I think
        "in": ("Invoice", "invoices"),
        "ii": ("Invoice item", "invoiceitems"),
        # products are covered in core resources
        # plans have a configurable id, though by default they are created with this pattern
        # 'plan': ('Plan', 'plans'),
        "sub": ("Subscription", "subscriptions"),
        "si": ("Subscription item", "subscription_items"),
        # I think usage records have URL prefixes like /subscription_items/si_id/usage_record_summaries
        "mbur": ("Usage record", None),
        # Undocumented :|
        "py": ("Payment", "payments"),
        "pyr": ("Refund", "refunds"),  # Pseudo refunds. Not fully tested.
        # Connect, Fraud, Orders, etc not implemented
    }
    name, url_prefix = names_and_urls[object_id.split("_")[0]]
    if lower:  # nocoverage
        name = name.lower()
    if url_prefix is None:  # nocoverage
        return name
    return f"[{name}](https://dashboard.stripe.com/{url_prefix}/{object_id})"


def stringify(value: object) -> str:
    if isinstance(value, int) and value > 1500000000 and value < 2000000000:
        return timestamp_to_datetime(value).strftime("%b %d, %Y, %H:%M:%S %Z")
    return str(value)
