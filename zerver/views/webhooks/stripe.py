# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string
from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

from datetime import datetime

@api_key_only_webhook_view('Stripe')
@has_request_variables
def api_stripe_webhook(request, user_profile, client,
                       payload=REQ(argument_type='body'), stream=REQ(default='test'),
                       topic=REQ(default='stripe')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], Text, Optional[Text]) -> HttpResponse
    body = ""
    event_type = ""
    body_template = ""
    data_object = payload["data"]["object"]
    try:
        event_type = payload["type"]
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

                body = body_template.format(amount=amount_string, rest=rest, verb=verb, charge=charge_id, link=link)

            else:
                charge_id = data_object["id"]
                link = charge_url.format(charge_id)
                body_template = "A charge with id **[{charge_id}]({link})** for **{amount}** has {verb}."

                if event_type == "charge.failed":
                    verb = "failed"
                else:
                    verb = "succeeded"
                body = body_template.format(charge_id=charge_id, link=link, amount=amount_string, verb=verb)

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

                else:
                    end_time = datetime.fromtimestamp(data_object["trial_end"]).strftime('%b %d %Y at %I:%M%p')
                    body_template = "The customer subscription trial with id **[{id}]({link})** will end on {time}"
                    body = body_template.format(id=object_id, link=link, time=end_time)

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

        elif event_type == "invoice.payment_failed":
            object_id = data_object['id']
            link = "https://dashboard.stripe.com/invoices/{}".format(object_id)
            amount_string = amount(data_object["amount_due"], data_object["currency"])
            body_template = "An invoice payment on invoice with id **[{id}]({link})** and "\
                            "with **{amount}** due has failed."
            body = body_template.format(id=object_id, amount=amount_string, link=link)

        elif event_type == "order.payment_failed":
            link = "https://dashboard.stripe.com/orders/"+payload["data"]["object"]["id"]
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            body_template = "An order payment on order with id **[{object[id]}](" + link + ")** for **" + amount_string + "** has failed."
            body = body_template.format(**(payload["data"]))
        elif event_type == "order.payment_succeeded":
            link = "https://dashboard.stripe.com/orders/"+payload["data"]["object"]["id"]
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            body_template = "An order payment on order with id **[{object[id]}](" + link + ")** for **"\
                            + amount_string + "** has succeeded."
            body = body_template.format(**(payload["data"]))
        elif event_type == "order.updated":
            link = "https://dashboard.stripe.com/orders/"+payload["data"]["object"]["id"]
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            body_template = "The order with id **[{object[id]}](" + link + ")** for **" + amount_string + "** has been updated."
            body = body_template.format(**(payload["data"]))
        elif event_type == "transfer.failed":
            link = "https://dashboard.stripe.com/transfers/"+payload["data"]["object"]["id"]
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            body_template = "The transfer with description **{object[description]}** and id **[{object[id]}]("\
                            + link + ")** for amount **"\
                            + amount_string + "** has failed."
            body = body_template.format(**(payload["data"]))
        elif event_type == "transfer.paid":
            link = "https://dashboard.stripe.com/transfers/"+payload["data"]["object"]["id"]
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            body_template = "The transfer with description **{object[description]}** and id **[{object[id]}]("\
                            + link + ")** for amount **"\
                            + amount_string + "** has been paid."
            body = body_template.format(**(payload["data"]))
    except KeyError as e:
        body = "Missing key {} in JSON".format(str(e))

    # send the message
    check_send_message(user_profile, client, 'stream', [stream], topic, body)

    return json_success()

def amount(amount, currency):
    # type: (int, str) -> str
    # zero-decimal currencies
    zero_decimal_currencies = ["bif", "djf", "jpy", "krw", "pyg", "vnd", "xaf", "xpf", "clp", "gnf", "kmf", "mga", "rwf", "vuv", "xof"]
    if currency in zero_decimal_currencies:
        return str(amount) + currency
    else:
        return '{0:.02f}'.format(float(amount) * 0.01) + currency
