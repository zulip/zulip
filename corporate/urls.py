from typing import Any

from django.conf.urls import include
from django.urls import path
from django.views.generic import TemplateView

from corporate.views.billing_page import billing_home, update_plan
from corporate.views.event_status import event_status, event_status_page
from corporate.views.session import (
    start_card_update_stripe_session,
    start_retry_payment_intent_session,
)
from corporate.views.support import support_request
from corporate.views.upgrade import initial_upgrade, sponsorship, upgrade
from corporate.views.webhook import stripe_webhook
from zerver.lib.rest import rest_path

i18n_urlpatterns: Any = [
    # Zephyr/MIT
    path("zephyr/", TemplateView.as_view(template_name="corporate/zephyr.html")),
    path("zephyr-mirror/", TemplateView.as_view(template_name="corporate/zephyr-mirror.html")),
    path("jobs/", TemplateView.as_view(template_name="corporate/jobs.html")),
    # Billing
    path("billing/", billing_home, name="billing_home"),
    path("upgrade/", initial_upgrade, name="initial_upgrade"),
    path("support/", support_request),
    path("billing/event_status/", event_status_page, name="event_status_page"),
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),
]

v1_api_and_json_patterns = [
    rest_path("billing/upgrade", POST=upgrade),
    rest_path("billing/sponsorship", POST=sponsorship),
    rest_path("billing/plan", PATCH=update_plan),
    rest_path("billing/session/start_card_update_session", POST=start_card_update_stripe_session),
    rest_path(
        "billing/session/start_retry_payment_intent_session",
        POST=start_retry_payment_intent_session,
    ),
    rest_path("billing/event/status", GET=event_status),
]

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]
