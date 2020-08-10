from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from zerver.decorator import require_realm_admin
from zerver.lib.actions import do_change_logo_source
from zerver.lib.realm_logo import get_realm_logo_url
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.upload import upload_logo_image
from zerver.lib.url_encoding import add_query_arg_to_redirect_url
from zerver.lib.validator import check_bool
from zerver.models import UserProfile


@require_realm_admin
@has_request_variables
def upload_logo(request: HttpRequest, user_profile: UserProfile,
                night: bool=REQ(validator=check_bool)) -> HttpResponse:
    user_profile.realm.ensure_not_on_limited_plan()

    if len(request.FILES) != 1:
        return json_error(_("You must upload exactly one logo."))
    logo_file = list(request.FILES.values())[0]
    if ((settings.MAX_LOGO_FILE_SIZE * 1024 * 1024) < logo_file.size):
        return json_error(_("Uploaded file is larger than the allowed limit of {} MiB").format(
            settings.MAX_LOGO_FILE_SIZE,
        ))
    upload_logo_image(logo_file, user_profile, night)
    do_change_logo_source(user_profile.realm, user_profile.realm.LOGO_UPLOADED, night, acting_user=user_profile)
    return json_success()

@require_realm_admin
@has_request_variables
def delete_logo_backend(request: HttpRequest, user_profile: UserProfile,
                        night: bool=REQ(validator=check_bool)) -> HttpResponse:
    # We don't actually delete the logo because it might still
    # be needed if the URL was cached and it is rewritten
    # in any case after next update.
    do_change_logo_source(user_profile.realm, user_profile.realm.LOGO_DEFAULT, night, acting_user=user_profile)
    return json_success()

@has_request_variables
def get_logo_backend(request: HttpRequest, user_profile: UserProfile,
                     night: bool=REQ(validator=check_bool)) -> HttpResponse:
    url = get_realm_logo_url(user_profile.realm, night)

    # We can rely on the url already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_logo_url does '?version=version_number'
    # hacks to prevent us from having to jump through decode/encode hoops.
    url = add_query_arg_to_redirect_url(url, request.META['QUERY_STRING'])
    return redirect(url)
