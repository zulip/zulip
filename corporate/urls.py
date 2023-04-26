from typing import Any

from django.conf.urls import include
from django.urls import path
from django.views.generic import RedirectView, TemplateView

from corporate.views.billing_page import billing_home, update_plan
from corporate.views.event_status import event_status, event_status_page
from corporate.views.portico import (
    app_download_link_redirect,
    apps_view,
    communities_view,
    hello_view,
    landing_view,
    plans_view,
    team_view,
)
from corporate.views.session import (
    start_card_update_stripe_session,
    start_retry_payment_intent_session,
)
from corporate.views.support import support_request
from corporate.views.upgrade import initial_upgrade, sponsorship, upgrade
from corporate.views.webhook import stripe_webhook
from zerver.lib.rest import rest_path
from zerver.lib.url_redirects import LANDING_PAGE_REDIRECTS

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

landing_page_urls = [
    # Landing page, features pages, signup form, etc.
    path("hello/", hello_view),
    path("features/", landing_view, {"template_name": "corporate/features.html"}),
    path("plans/", plans_view, name="plans"),
    path("apps/", apps_view),
    path("apps/download/<platform>", app_download_link_redirect),
    path("apps/<platform>", apps_view),
    path(
        "development-community/",
        landing_view,
        {"template_name": "corporate/development-community.html"},
    ),
    path("attribution/", landing_view, {"template_name": "corporate/attribution.html"}),
    path("team/", team_view),
    path("history/", landing_view, {"template_name": "corporate/history.html"}),
    path("values/", landing_view, {"template_name": "corporate/values.html"}),
    path("why-zulip/", landing_view, {"template_name": "corporate/why-zulip.html"}),
    path("self-hosting/", landing_view, {"template_name": "corporate/self-hosting.html"}),
    path("security/", landing_view, {"template_name": "corporate/security.html"}),
    path("try-zulip/", landing_view, {"template_name": "corporate/try-zulip.html"}),
    # /for pages
    path("use-cases/", landing_view, {"template_name": "corporate/for/use-cases.html"}),
    path(
        "for/communities/",
        landing_view,
        {"template_name": "corporate/for/communities.html"},
    ),
    path("for/education/", landing_view, {"template_name": "corporate/for/education.html"}),
    path("for/events/", landing_view, {"template_name": "corporate/for/events.html"}),
    path("for/open-source/", landing_view, {"template_name": "corporate/for/open-source.html"}),
    path("for/research/", landing_view, {"template_name": "corporate/for/research.html"}),
    path("for/business/", landing_view, {"template_name": "corporate/for/business.html"}),
    # case-studies
    path(
        "case-studies/idrift/",
        landing_view,
        {"template_name": "corporate/case-studies/idrift-case-study.html"},
    ),
    path(
        "case-studies/end-point/",
        landing_view,
        {"template_name": "corporate/case-studies/end-point-case-study.html"},
    ),
    path(
        "case-studies/atolio/",
        landing_view,
        {"template_name": "corporate/case-studies/atolio-case-study.html"},
    ),
    path(
        "case-studies/tum/",
        landing_view,
        {"template_name": "corporate/case-studies/tum-case-study.html"},
    ),
    path(
        "case-studies/ucsd/",
        landing_view,
        {"template_name": "corporate/case-studies/ucsd-case-study.html"},
    ),
    path(
        "case-studies/rust/",
        landing_view,
        {"template_name": "corporate/case-studies/rust-case-study.html"},
    ),
    path(
        "case-studies/lean/",
        landing_view,
        {"template_name": "corporate/case-studies/lean-case-study.html"},
    ),
    path(
        "case-studies/asciidoctor/",
        landing_view,
        {"template_name": "corporate/case-studies/asciidoctor-case-study.html"},
    ),
    path(
        "case-studies/recurse-center/",
        landing_view,
        {"template_name": "corporate/case-studies/recurse-center-case-study.html"},
    ),
    path("communities/", communities_view),
]

# Redirects due to us having moved or combined landing pages:
for redirect in LANDING_PAGE_REDIRECTS:
    old_url = redirect.old_url.lstrip("/")
    landing_page_urls += [path(old_url, RedirectView.as_view(url=redirect.new_url, permanent=True))]

i18n_urlpatterns += landing_page_urls

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]
