from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from zerver.context_processors import get_realm_from_request
from zerver.decorator import do_login, require_post
from zerver.lib.exceptions import (
    AuthenticationFailedError,
    InvalidSubdomainError,
    JsonableError,
    RealmDeactivatedError,
    UserDeactivatedError,
)
from zerver.lib.response import json_success
from zerver.lib.subdomains import get_subdomain
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import validate_login_email
from zerver.models import Realm, UserProfile
from zerver.models.realms import get_realm
from zerver.views.auth import get_safe_redirect_to
from zerver.views.errors import config_error
from zproject.backends import dev_auth_enabled


def get_dev_users(realm: Realm | None = None, extra_users_count: int = 10) -> list[UserProfile]:
    # Development environments usually have only a few users, but
    # it still makes sense to limit how many extra users we render to
    # support performance testing with DevAuthBackend.
    if realm is not None:
        users_query = UserProfile.objects.select_related("realm").filter(
            is_bot=False, is_active=True, realm=realm
        )
    else:
        users_query = UserProfile.objects.select_related("realm").filter(
            is_bot=False, is_active=True
        )

    shakespearian_users = users_query.exclude(email__startswith="extrauser").order_by("email")
    extra_users = users_query.filter(email__startswith="extrauser").order_by("email")
    # Limit the number of extra users we offer by default
    extra_users = extra_users[0:extra_users_count]
    users = [*shakespearian_users, *extra_users]
    return users


def add_dev_login_context(realm: Realm | None, context: dict[str, Any]) -> None:
    users = get_dev_users(realm)
    context["current_realm"] = realm
    context["all_realms"] = Realm.objects.filter(deactivated_redirect__isnull=True)

    def sort(lst: list[UserProfile]) -> list[UserProfile]:
        return sorted(lst, key=lambda u: u.delivery_email)

    context["direct_owners"] = sort([u for u in users if u.is_realm_owner])
    context["direct_admins"] = sort([u for u in users if u.is_realm_admin and not u.is_realm_owner])
    context["guest_users"] = sort([u for u in users if u.is_guest])
    context["direct_moderators"] = sort([u for u in users if u.role == UserProfile.ROLE_MODERATOR])
    context["direct_users"] = sort([u for u in users if not (u.is_guest or u.is_moderator)])


@csrf_exempt
@typed_endpoint
def dev_direct_login(
    request: HttpRequest,
    *,
    next: str = "/",
) -> HttpResponse:
    # This function allows logging in without a password and should only be called
    # in development environments.  It may be called if the DevAuthBackend is included
    # in settings.AUTHENTICATION_BACKENDS
    if (not dev_auth_enabled()) or settings.PRODUCTION:
        # This check is probably not required, since authenticate would fail without
        # an enabled DevAuthBackend.
        return config_error(request, "dev_not_supported")

    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)

    if request.POST.get("prefers_web_public_view") == "Anonymous login":
        redirect_to = get_safe_redirect_to(next, realm.url)
        return HttpResponseRedirect(redirect_to)

    email = request.POST["direct_email"]
    user_profile = authenticate(dev_auth_username=email, realm=realm)
    if user_profile is None:
        return config_error(request, "dev_not_supported")
    assert isinstance(user_profile, UserProfile)
    do_login(request, user_profile)

    redirect_to = get_safe_redirect_to(next, user_profile.realm.url)
    return HttpResponseRedirect(redirect_to)


def check_dev_auth_backend() -> None:
    if settings.PRODUCTION:
        raise JsonableError(_("Endpoint not available in production."))
    if not dev_auth_enabled():
        raise JsonableError(_("DevAuthBackend not enabled."))


@csrf_exempt
@require_post
@typed_endpoint
def api_dev_fetch_api_key(request: HttpRequest, *, username: str) -> HttpResponse:
    """This function allows logging in without a password on the Zulip
    mobile apps when connecting to a Zulip development environment.  It
    requires DevAuthBackend to be included in settings.AUTHENTICATION_BACKENDS.
    """
    check_dev_auth_backend()

    # Django invokes authenticate methods by matching arguments, and this
    # authentication flow will not invoke LDAP authentication because of
    # this condition of Django so no need to check if LDAP backend is
    # enabled.
    validate_login_email(username)
    realm = get_realm_from_request(request)
    if realm is None:
        raise InvalidSubdomainError
    return_data: dict[str, bool] = {}
    user_profile = authenticate(dev_auth_username=username, realm=realm, return_data=return_data)
    if return_data.get("inactive_realm"):
        raise RealmDeactivatedError
    if return_data.get("inactive_user"):
        raise UserDeactivatedError
    if return_data.get("invalid_subdomain"):  # nocoverage
        raise InvalidSubdomainError
    if user_profile is None:
        # Since we're not actually checking passwords, this condition
        # is when one's attempting to send an email address that
        # doesn't have an account, i.e. it's definitely invalid username.
        raise AuthenticationFailedError
    assert isinstance(user_profile, UserProfile)

    do_login(request, user_profile)
    api_key = user_profile.api_key
    return json_success(
        request,
        data={"api_key": api_key, "email": user_profile.delivery_email, "user_id": user_profile.id},
    )


@csrf_exempt
def api_dev_list_users(request: HttpRequest) -> HttpResponse:
    check_dev_auth_backend()

    users = get_dev_users()
    return json_success(
        request,
        data=dict(
            direct_admins=[
                dict(email=u.delivery_email, realm_url=u.realm.url)
                for u in users
                if u.is_realm_admin
            ],
            direct_users=[
                dict(email=u.delivery_email, realm_url=u.realm.url)
                for u in users
                if not u.is_realm_admin
            ],
        ),
    )
