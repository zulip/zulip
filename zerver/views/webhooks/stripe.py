# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string
from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Dict, Any, Iterable, Optional

from datetime import datetime

@api_key_only_webhook_view('Stripe')
@has_request_variables
def api_stripe_webhook(request, user_profile, client,
                       payload=REQ(argument_type='body'), stream=REQ(default='test'),
                       topic=REQ(default='stripe')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], text_type, Optional[text_type]) -> HttpResponse
    body = ""
    event_type = ""
    try:
        event_type = payload["type"]
        if event_type == "charge.dispute.closed":
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            link = "https://dashboard.stripe.com/payments/"+payload["data"]["object"]["charge"]
            body_template = "A charge dispute for **" + amount_string + "** has been closed as **{object[status]}**.\n"\
                            + "The charge in dispute was **[{object[charge]}](" + link + ")**."
            body = body_template.format(**(payload["data"]))
        elif event_type == "charge.dispute.created":
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            link = "https://dashboard.stripe.com/payments/"+payload["data"]["object"]["charge"]
            body_template = "A charge dispute for **" + amount_string + "** has been created.\n"\
                            + "The charge in dispute is **[{object[charge]}](" + link + ")**."
            body = body_template.format(**(payload["data"]))
        elif event_type == "charge.failed":
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            link = "https://dashboard.stripe.com/payments/"+payload["data"]["object"]["id"]
            body_template = "A charge with id **[{object[id]}](" + link + ")** for **" + amount_string + "** has failed."
            body = body_template.format(**(payload["data"]))
        elif event_type == "charge.succeeded":
            amount_string = amount(payload["data"]["object"]["amount"], payload["data"]["object"]["currency"])
            link = "https://dashboard.stripe.com/payments/"+payload["data"]["object"]["id"]
            body_template = "A charge with id **[{object[id]}](" + link + ")** for **" + amount_string + "** has succeeded."
            body = body_template.format(**(payload["data"]))
        elif event_type == "customer.created":
            link = "https://dashboard.stripe.com/customers/"+payload["data"]["object"]["id"]
            if payload["data"]["object"]["email"] is None:
                body_template = "A new customer with id **[{object[id]}](" + link + ")** has been created."
                body = body_template.format(**(payload["data"]))
            else:
                body_template = "A new customer with id **[{object[id]}](" + link + ")** and email **{object[email]}** has been created."
                body = body_template.format(**(payload["data"]))
        elif event_type == "customer.deleted":
            link = "https://dashboard.stripe.com/customers/"+payload["data"]["object"]["id"]
            body_template = "A customer with id **[{object[id]}](" + link + ")** has been deleted."
            body = body_template.format(**(payload["data"]))
        elif event_type == "customer.subscription.created":
            amount_string = amount(payload["data"]["object"]["plan"]["amount"], payload["data"]["object"]["plan"]["currency"])
            link = "https://dashboard.stripe.com/subscriptions/"+payload["data"]["object"]["id"]
            body_template = "A new customer subscription for **" + amount_string + "** every **{plan[interval]}** has been created.\n"
            body_template += "The subscription has id **[{id}](" + link + ")**."
            body = body_template.format(**(payload["data"]["object"]))
        elif event_type == "customer.subscription.deleted":
            link = "https://dashboard.stripe.com/subscriptions/"+payload["data"]["object"]["id"]
            body_template = "The customer subscription with id **[{object[id]}](" + link + ")** was deleted."
            body = body_template.format(**(payload["data"]))
        elif event_type == "customer.subscription.trial_will_end":
            link = "https://dashboard.stripe.com/subscriptions/"+payload["data"]["object"]["id"]
            body_template = "The customer subscription trial with id **[{object[id]}](" + link + ")** will end on "
            body_template += datetime.fromtimestamp(payload["data"]["object"]["trial_end"]).strftime('%b %d %Y at %I:%M%p')
            body = body_template.format(**(payload["data"]))
        elif event_type == "invoice.payment_failed":
            link = "https://dashboard.stripe.com/invoices/"+payload["data"]["object"]["id"]
            amount_string = amount(payload["data"]["object"]["amount_due"], payload["data"]["object"]["currency"])
            body_template = "An invoice payment on invoice with id **[{object[id]}](" + link + ")** and with **"\
                            + amount_string + "** due has failed."
            body = body_template.format(**(payload["data"]))
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
