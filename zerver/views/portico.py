
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
import ujson

from zerver.context_processors import get_realm_from_request
from zerver.decorator import redirect_to_login
from zerver.lib.storage import static_path
from zerver.models import Realm

def apps_view(request: HttpRequest, _: str) -> HttpResponse:
    if settings.ZILENCER_ENABLED:
        return render(request, 'zerver/apps.html')
    return HttpResponseRedirect('https://zulipchat.com/apps/', status=301)

def plans_view(request: HttpRequest) -> HttpResponse:
    realm = get_realm_from_request(request)
    realm_plan_type = 0
    if realm is not None:
        realm_plan_type = realm.plan_type
        if realm.plan_type == Realm.SELF_HOSTED and settings.PRODUCTION:
            return HttpResponseRedirect('https://zulipchat.com/plans')
        if not request.user.is_authenticated:
            return redirect_to_login(next="plans")
    return render(request, "zerver/plans.html", context={"realm_plan_type": realm_plan_type})

def team_view(request: HttpRequest) -> HttpResponse:
    with open(static_path('generated/github-contributors.json')) as f:
        data = ujson.load(f)

    return render(
        request,
        'zerver/team.html',
        context={
            'page_params': {
                'contrib': data['contrib'],
            },
            'date': data['date'],
        },
    )
