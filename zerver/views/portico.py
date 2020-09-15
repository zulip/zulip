from typing import Optional

import orjson
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse

from version import LATEST_DESKTOP_VERSION
from zerver.context_processors import get_realm_from_request, latest_info_context
from zerver.decorator import add_google_analytics
from zerver.models import Realm


@add_google_analytics
def apps_view(request: HttpRequest, platform: Optional[str] = None) -> HttpResponse:
    if settings.ZILENCER_ENABLED:
        return TemplateResponse(
            request,
            'zerver/apps.html',
            context={
                "page_params": {
                    'electron_app_version': LATEST_DESKTOP_VERSION,
                },
            },
        )
    return HttpResponseRedirect('https://zulip.com/apps/', status=301)

@add_google_analytics
def plans_view(request: HttpRequest) -> HttpResponse:
    realm = get_realm_from_request(request)
    realm_plan_type = 0
    free_trial_days = settings.FREE_TRIAL_DAYS
    sponsorship_pending = False

    if realm is not None:
        realm_plan_type = realm.plan_type
        if realm.plan_type == Realm.SELF_HOSTED and settings.PRODUCTION:
            return HttpResponseRedirect('https://zulip.com/plans')
        if not request.user.is_authenticated:
            return redirect_to_login(next="plans")
        if request.user.is_guest:
            return TemplateResponse(request, "404.html", status=404)
        if settings.CORPORATE_ENABLED:
            from corporate.models import get_customer_by_realm
            customer = get_customer_by_realm(realm)
            if customer is not None:
                sponsorship_pending = customer.sponsorship_pending

    return TemplateResponse(
        request,
        "zerver/plans.html",
        context={"realm_plan_type": realm_plan_type, 'free_trial_days': free_trial_days, 'sponsorship_pending': sponsorship_pending},
    )

@add_google_analytics
def team_view(request: HttpRequest) -> HttpResponse:
    if not settings.ZILENCER_ENABLED:
        return HttpResponseRedirect('https://zulip.com/team/', status=301)

    try:
        with open(settings.CONTRIBUTOR_DATA_FILE_PATH, "rb") as f:
            data = orjson.loads(f.read())
    except FileNotFoundError:
        data = {'contributors': {}, 'date': "Never ran."}

    return TemplateResponse(
        request,
        'zerver/team.html',
        context={
            'page_params': {
                'contributors': data['contributors'],
            },
            'date': data['date'],
        },
    )

def get_isolated_page(request: HttpRequest) -> bool:
    '''Accept a GET param `?nav=no` to render an isolated, navless page.'''
    return request.GET.get('nav') == 'no'

@add_google_analytics
def landing_view(request: HttpRequest, template_name: str) -> HttpResponse:
    return TemplateResponse(request, template_name)

@add_google_analytics
def hello_view(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(request, 'zerver/hello.html', latest_info_context())

@add_google_analytics
def terms_view(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request, 'zerver/terms.html',
        context={'isolated_page': get_isolated_page(request)},
    )

@add_google_analytics
def privacy_view(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request, 'zerver/privacy.html',
        context={'isolated_page': get_isolated_page(request)},
    )
