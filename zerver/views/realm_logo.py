from django.conf import settings
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.http import HttpResponse, HttpRequest

from zerver.lib.validator import check_bool
from zerver.lib.request import REQ, has_request_variables
from zerver.decorator import require_realm_admin
from zerver.lib.actions import do_change_logo_source
from zerver.lib.realm_logo import realm_logo_url
from zerver.lib.response import json_error, json_success
from zerver.lib.upload import upload_logo_image
from zerver.models import Realm, UserProfile


@require_realm_admin
@has_request_variables
def upload_logo(request: HttpRequest, user_profile: UserProfile,
                night: bool=REQ(validator=check_bool)) -> HttpResponse:
    if user_profile.realm.plan_type == Realm.LIMITED:
        return json_error(_("Feature unavailable on your current plan."))

    if len(request.FILES) != 1:
        return json_error(_("You must upload exactly one logo."))
    logo_file = list(request.FILES.values())[0]
    if ((settings.MAX_LOGO_FILE_SIZE * 1024 * 1024) < logo_file.size):
        return json_error(_("Uploaded file is larger than the allowed limit of %s MB") % (
            settings.MAX_LOGO_FILE_SIZE))
    upload_logo_image(logo_file, user_profile, night)
    do_change_logo_source(user_profile.realm, user_profile.realm.LOGO_UPLOADED, night)
    logo_url = realm_logo_url(user_profile.realm, night)
    if night:
        json_result = dict(
            night_logo_url=logo_url
        )
    else:
        json_result = dict(
            logo_url=logo_url
        )
    return json_success(json_result)

@require_realm_admin
@has_request_variables
def delete_logo_backend(request: HttpRequest, user_profile: UserProfile,
                        night: bool=REQ(validator=check_bool)) -> HttpResponse:
    # We don't actually delete the logo because it might still
    # be needed if the URL was cached and it is rewrited
    # in any case after next update.
    do_change_logo_source(user_profile.realm, user_profile.realm.LOGO_DEFAULT, night)
    default_url = realm_logo_url(user_profile.realm, night)
    if night:
        json_result = dict(
            night_logo_url=default_url
        )
    else:
        json_result = dict(
            logo_url=default_url
        )
    return json_success(json_result)

@has_request_variables
def get_logo_backend(request: HttpRequest, user_profile: UserProfile,
                     night: bool=REQ(validator=check_bool)) -> HttpResponse:
    url = realm_logo_url(user_profile.realm, night)

    # We can rely on the url already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_logo_url does '?version=version_number'
    # hacks to prevent us from having to jump through decode/encode hoops.
    assert '?' in url
    url += '&' + request.META['QUERY_STRING']
    return redirect(url)
