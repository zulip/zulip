from typing import Optional
from urllib.parse import urlencode

import orjson
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse

from corporate.lib.stripe import is_realm_on_free_trial
from corporate.models import get_customer_by_realm
from zerver.context_processors import get_realm_from_request, latest_info_context
from zerver.decorator import add_google_analytics
from zerver.lib.github import (
    InvalidPlatformError,
    get_latest_github_release_download_link_for_platform,
)
from zerver.lib.realm_description import get_realm_text_description
from zerver.lib.realm_icon import get_realm_icon_url
from zerver.lib.subdomains import is_subdomain_root_or_alias
from zerver.models import Realm


@add_google_analytics
def apps_view(request: HttpRequest, platform: Optional[str] = None) -> HttpResponse:
    if not settings.CORPORATE_ENABLED:
        # This seems impossible (CORPORATE_ENABLED set to false when
        # rendering a "corporate" view) -- but we add it to make
        # testing possible.  Tests default to running with the
        # "corporate" app installed, and unsetting that is difficult,
        # as one cannot easily reload the URL resolution -- so we add
        # a redirect here, equivalent to the one zerver would have
        # installed when "corporate" is not enabled, to make the
        # behaviour testable with CORPORATE_ENABLED set to false.
        return HttpResponseRedirect("https://zulip.com/apps/", status=301)
    return TemplateResponse(
        request,
        "corporate/apps.html",
    )


def app_download_link_redirect(request: HttpRequest, platform: str) -> HttpResponse:
    try:
        download_link = get_latest_github_release_download_link_for_platform(platform)
        return HttpResponseRedirect(download_link, status=302)
    except InvalidPlatformError:
        return TemplateResponse(request, "404.html", status=404)


@add_google_analytics
def plans_view(request: HttpRequest) -> HttpResponse:
    realm = get_realm_from_request(request)
    free_trial_days = settings.FREE_TRIAL_DAYS
    sponsorship_pending = False
    sponsorship_url = "/upgrade/#sponsorship"
    if is_subdomain_root_or_alias(request):
        # If we're on the root domain, we make this link first ask you which organization.
        sponsorship_url = f"/accounts/go/?{urlencode({'next': sponsorship_url})}"
    realm_on_free_trial = False

    if realm is not None:
        if realm.plan_type == Realm.PLAN_TYPE_SELF_HOSTED and settings.PRODUCTION:
            return HttpResponseRedirect("https://zulip.com/plans/")
        if not request.user.is_authenticated:
            return redirect_to_login(next="/plans/")
        if request.user.is_guest:
            return TemplateResponse(request, "404.html", status=404)
        customer = get_customer_by_realm(realm)
        if customer is not None:
            sponsorship_pending = customer.sponsorship_pending
            realm_on_free_trial = is_realm_on_free_trial(realm)

    return TemplateResponse(
        request,
        "corporate/plans.html",
        context={
            "realm": realm,
            "free_trial_days": free_trial_days,
            "realm_on_free_trial": realm_on_free_trial,
            "sponsorship_pending": sponsorship_pending,
            "sponsorship_url": sponsorship_url,
        },
    )


@add_google_analytics
def team_view(request: HttpRequest) -> HttpResponse:
    if not settings.ZILENCER_ENABLED:
        return HttpResponseRedirect("https://zulip.com/team/", status=301)

    try:
        with open(settings.CONTRIBUTOR_DATA_FILE_PATH, "rb") as f:
            data = orjson.loads(f.read())
    except FileNotFoundError:
        data = {"contributors": [], "date": "Never ran."}

    return TemplateResponse(
        request,
        "corporate/team.html",
        context={
            "page_params": {
                "contributors": data["contributors"],
            },
            "date": data["date"],
        },
    )


@add_google_analytics
def landing_view(request: HttpRequest, template_name: str) -> HttpResponse:
    return TemplateResponse(request, template_name, latest_info_context())


@add_google_analytics
def hello_view(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(request, "corporate/hello.html", latest_info_context())


@add_google_analytics
def communities_view(request: HttpRequest) -> HttpResponse:
    eligible_realms = []
    unique_org_type_ids = set()
    want_to_be_advertised_realms = Realm.objects.filter(
        want_advertise_in_communities_directory=True
    ).order_by("name")
    for realm in want_to_be_advertised_realms:
        open_to_public = not realm.invite_required and not realm.emails_restricted_to_domains
        if realm.allow_web_public_streams_access() or open_to_public:
            [org_type] = (
                org_type
                for org_type in Realm.ORG_TYPES
                if Realm.ORG_TYPES[org_type]["id"] == realm.org_type
            )
            eligible_realms.append(
                {
                    "id": realm.id,
                    "name": realm.name,
                    "realm_url": realm.uri,
                    "logo_url": get_realm_icon_url(realm),
                    "description": get_realm_text_description(realm),
                    "org_type_key": org_type,
                }
            )
            unique_org_type_ids.add(realm.org_type)

    # Remove org_types for which there are no open organizations.
    org_types = dict()
    for org_type in Realm.ORG_TYPES:
        if Realm.ORG_TYPES[org_type]["id"] in unique_org_type_ids:
            org_types[org_type] = Realm.ORG_TYPES[org_type]

        # Remove `Unspecified` ORG_TYPE
        org_types.pop("unspecified", None)

    # Change display name of non-profit orgs.
    if org_types.get("nonprofit"):  # nocoverage
        org_types["nonprofit"]["name"] = "Non-profit"

    return TemplateResponse(
        request,
        "corporate/communities.html",
        context={
            "eligible_realms": eligible_realms,
            "org_types": org_types,
        },
    )
