from typing import Any

from django.conf.urls import include
from django.urls import path
from django.views.generic import RedirectView, TemplateView

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
from zerver.views.portico import (
    app_download_link_redirect,
    apps_view,
    hello_view,
    landing_view,
    plans_view,
    team_view,
)

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
    path("new-user/", RedirectView.as_view(url="/hello", permanent=True)),
    path("features/", landing_view, {"template_name": "zerver/features.html"}),
    path("plans/", plans_view, name="plans"),
    path("apps/", apps_view),
    path("apps/download/<platform>", app_download_link_redirect),
    path("apps/<platform>", apps_view),
    path(
        "developer-community/", RedirectView.as_view(url="/development-community/", permanent=True)
    ),
    path(
        "development-community/",
        landing_view,
        {"template_name": "zerver/development-community.html"},
    ),
    path("attribution/", landing_view, {"template_name": "zerver/attribution.html"}),
    path("team/", team_view),
    path("history/", landing_view, {"template_name": "zerver/history.html"}),
    path("why-zulip/", landing_view, {"template_name": "zerver/why-zulip.html"}),
    path("self-hosting/", landing_view, {"template_name": "zerver/self-hosting.html"}),
    path("security/", landing_view, {"template_name": "zerver/security.html"}),
    # /for pages
    path("use-cases/", landing_view, {"template_name": "zerver/use-cases.html"}),
    path("for/education/", landing_view, {"template_name": "zerver/for-education.html"}),
    path("for/events/", landing_view, {"template_name": "zerver/for-events.html"}),
    path("for/open-source/", landing_view, {"template_name": "zerver/for-open-source.html"}),
    path("for/research/", landing_view, {"template_name": "zerver/for-research.html"}),
    path("for/business/", landing_view, {"template_name": "zerver/for-business.html"}),
    path("for/companies/", RedirectView.as_view(url="/for/business/", permanent=True)),
    path(
        "for/communities/",
        landing_view,
        {"template_name": "zerver/for-communities.html"},
    ),
    # We merged this into /for/communities.
    path(
        "for/working-groups-and-communities/",
        RedirectView.as_view(url="/for/communities/", permanent=True),
    ),
    # case-studies
    path("case-studies/idrift/", landing_view, {"template_name": "zerver/idrift-case-study.html"}),
    path("case-studies/tum/", landing_view, {"template_name": "zerver/tum-case-study.html"}),
    path("case-studies/ucsd/", landing_view, {"template_name": "zerver/ucsd-case-study.html"}),
    path("case-studies/rust/", landing_view, {"template_name": "zerver/rust-case-study.html"}),
    path("case-studies/lean/", landing_view, {"template_name": "zerver/lean-case-study.html"}),
    path(
        "case-studies/asciidoctor/",
        landing_view,
        {"template_name": "zerver/asciidoctor-case-study.html"},
    ),
    path(
        "case-studies/recurse-center/",
        landing_view,
        {"template_name": "zerver/recurse-center-case-study.html"},
    ),
]
i18n_urlpatterns += landing_page_urls

# Make a copy of i18n_urlpatterns so that they appear without prefix for English
urlpatterns = list(i18n_urlpatterns)

urlpatterns += [
    path("api/v1/", include(v1_api_and_json_patterns)),
    path("json/", include(v1_api_and_json_patterns)),
]
