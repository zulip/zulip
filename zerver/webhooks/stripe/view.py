# Webhooks for external integrations.
import time
from datetime import datetime
from typing import Any, Dict, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@api_key_only_webhook_view('Stripe')
@has_request_variables
def api_stripe_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body'),
                       stream: Text=REQ(default='test')) -> HttpResponse:
    body = None
    event_type = payload["type"]
    data_object = payload["data"]["object"]
    if event_type.startswith('charge'):

        charge_url = "https://dashboard.stripe.com/payments/{}"
        amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])

        if event_type.startswith('charge.dispute'):
            charge_id = data_object["charge"]
            link = charge_url.format(charge_id)
            body_template = "A charge dispute for **{amount}** has been {rest}.\n"\
                            "The charge in dispute {verb} **[{charge}]({link})**."

            if event_type == "charge.dispute.closed":
                rest = "closed as **{}**".format(data_object['status'])
                verb = 'was'
            else:
                rest = "created"
                verb = 'is'

            body = body_template.format(amount=amount_string,
                                        rest=rest,
                                        verb=verb,
                                        charge=charge_id,
                                        link=link)

        else:
            charge_id = data_object["id"]
            link = charge_url.format(charge_id)
            body_template = "A charge with id **[{charge_id}]({link})** for **{amount}** has {verb}."

            if event_type == "charge.failed":
                verb = "failed"
            else:
                verb = "succeeded"
            body = body_template.format(charge_id=charge_id, link=link, amount=amount_string, verb=verb)

        topic = "Charge {}".format(charge_id)

    elif event_type.startswith('customer'):
        object_id = data_object["id"]
        if event_type.startswith('customer.subscription'):
            link = "https://dashboard.stripe.com/subscriptions/{}".format(object_id)

            if event_type == "customer.subscription.created":
                amount_string = amount(data_object["plan"]["amount"], data_object["plan"]["currency"])

                body_template = "A new customer subscription for **{amount}** " \
                                "every **{interval}** has been created.\n" \
                                "The subscription has id **[{id}]({link})**."
                body = body_template.format(
                    amount=amount_string,
                    interval=data_object['plan']['interval'],
                    id=object_id,
                    link=link
                )

            elif event_type == "customer.subscription.deleted":
                body_template = "The customer subscription with id **[{id}]({link})** was deleted."
                body = body_template.format(id=object_id, link=link)

            else:  # customer.subscription.trial_will_end
                DAY = 60 * 60 * 24  # seconds in a day
                # days_left should always be three according to
                # https://stripe.com/docs/api/python#event_types, but do the
                # computation just to be safe.
                days_left = int((data_object["trial_end"] - time.time() + DAY//2) // DAY)
                body_template = ("The customer subscription trial with id"
                                 " **[{id}]({link})** will end in {days} days.")
                body = body_template.format(id=object_id, link=link, days=days_left)

        else:
            link = "https://dashboard.stripe.com/customers/{}".format(object_id)
            body_template = "{beginning} customer with id **[{id}]({link})** {rest}."

            if event_type == "customer.created":
                beginning = "A new"
                if data_object["email"] is None:
                    rest = "has been created"
                else:
                    rest = "and email **{}** has been created".format(data_object['email'])
            else:
                beginning = "A"
                rest = "has been deleted"
            body = body_template.format(beginning=beginning, id=object_id, link=link, rest=rest)

        topic = "Customer {}".format(object_id)

    elif event_type == "invoice.payment_failed":
        object_id = data_object['id']
        link = "https://dashboard.stripe.com/invoices/{}".format(object_id)
        amount_string = amount(data_object["amount_due"], data_object["currency"])
        body_template = "An invoice payment on invoice with id **[{id}]({link})** and "\
                        "with **{amount}** due has failed."
        body = body_template.format(id=object_id, amount=amount_string, link=link)
        topic = "Invoice {}".format(object_id)

    elif event_type.startswith('order'):
        object_id = data_object['id']
        link = "https://dashboard.stripe.com/orders/{}".format(object_id)
        amount_string = amount(data_object["amount"], data_object["currency"])
        body_template = "{beginning} order with id **[{id}]({link})** for **{amount}** has {end}."

        if event_type == "order.payment_failed":
            beginning = "An order payment on"
            end = "failed"
        elif event_type == "order.payment_succeeded":
            beginning = "An order payment on"
            end = "succeeded"
        else:
            beginning = "The"
            end = "been updated"

        body = body_template.format(beginning=beginning,
                                    id=object_id,
                                    link=link,
                                    amount=amount_string,
                                    end=end)
        topic = "Order {}".format(object_id)

    elif event_type.startswith('transfer'):
        object_id = data_object['id']
        link = "https://dashboard.stripe.com/transfers/{}".format(object_id)
        amount_string = amount(data_object["amount"], data_object["currency"])
        body_template = "The transfer with description **{description}** and id **[{id}]({link})** " \
                        "for amount **{amount}** has {end}."
        if event_type == "transfer.failed":
            end = 'failed'
        else:
            end = "been paid"
        body = body_template.format(
            description=data_object['description'],
            id=object_id,
            link=link,
            amount=amount_string,
            end=end
        )
        topic = "Transfer {}".format(object_id)

    if body is None:
        return json_error(_("We don't support {} event".format(event_type)))

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

def amount(amount: int, currency: str) -> str:
    # zero-decimal currencies
    zero_decimal_currencies = ["bif", "djf", "jpy", "krw", "pyg", "vnd", "xaf",
                               "xpf", "clp", "gnf", "kmf", "mga", "rwf", "vuv", "xof"]
    if currency in zero_decimal_currencies:
        return str(amount) + currency
    else:
        return '{0:.02f}'.format(float(amount) * 0.01) + currency
