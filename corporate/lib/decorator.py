import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Concatenate
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from typing_extensions import ParamSpec

from corporate.lib.remote_billing_util import (
    RemoteBillingIdentityExpiredError,
    get_remote_realm_and_user_from_session,
    get_remote_server_and_user_from_session,
)
from zerver.lib.exceptions import RemoteBillingAuthenticationError
from zerver.lib.subdomains import get_subdomain
from zerver.lib.url_encoding import append_url_query_string
from zilencer.models import RemoteRealm

if TYPE_CHECKING:
    from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession

ParamT = ParamSpec("ParamT")


def session_expired_ajax_response(login_url: str) -> JsonResponse:  # nocoverage
    return JsonResponse(
        {
            "error_message": "Remote billing authentication expired",
            "login_url": login_url,
        },
        status=401,
    )


def is_self_hosting_management_subdomain(request: HttpRequest) -> bool:
    subdomain = get_subdomain(request)
    return subdomain == settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN


def self_hosting_management_endpoint(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        if not is_self_hosting_management_subdomain(request):  # nocoverage
            return render(request, "404.html", status=404)
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def authenticated_remote_realm_management_endpoint(
    view_func: Callable[
        Concatenate[HttpRequest, "RemoteRealmBillingSession", ParamT], HttpResponse
    ],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        from corporate.lib.stripe import RemoteRealmBillingSession

        if not is_self_hosting_management_subdomain(request):  # nocoverage
            return render(request, "404.html", status=404)

        realm_uuid = kwargs.pop("realm_uuid")
        if realm_uuid is not None and not isinstance(realm_uuid, str):  # nocoverage
            raise TypeError("realm_uuid must be a string or None")

        try:
            remote_realm, remote_billing_user = get_remote_realm_and_user_from_session(
                request, realm_uuid
            )
        except RemoteBillingIdentityExpiredError as e:
            # The user had an authenticated session with an identity_dict,
            # but it expired.
            # We want to redirect back to the start of their login flow
            # at their {realm.host}/self-hosted-billing/ with a proper
            # next parameter to take them back to what they're trying
            # to access after re-authing.
            # Note: Theoretically we could take the realm_uuid from the request
            # path or params to figure out the remote_realm.host for the redirect,
            # but that would mean leaking that .host value to anyone who knows
            # the uuid. Therefore we limit ourselves to taking the realm_uuid
            # from the identity_dict - since that proves that the user at least
            # previously was successfully authenticated as a billing admin of that
            # realm.
            realm_uuid = e.realm_uuid
            server_uuid = e.server_uuid
            uri_scheme = e.uri_scheme
            if realm_uuid is None:
                # This doesn't make sense - if get_remote_realm_and_user_from_session
                # found an expired identity dict, it should have had a realm_uuid.
                raise AssertionError

            assert server_uuid is not None, "identity_dict with realm_uuid must have server_uuid"
            assert uri_scheme is not None, "identity_dict with realm_uuid must have uri_scheme"

            try:
                remote_realm = RemoteRealm.objects.get(uuid=realm_uuid, server__uuid=server_uuid)
            except RemoteRealm.DoesNotExist:
                # This should be impossible - unless the RemoteRealm existed and somehow the row
                # was deleted.
                raise AssertionError

            # Using EXTERNAL_URI_SCHEME means we'll do https:// in production, which is
            # the sane default - while having http:// in development, which will allow
            # these redirects to work there for testing.
            url = urljoin(uri_scheme + remote_realm.host, "/self-hosted-billing/")

            page_type = get_next_page_param_from_request_path(request)
            if page_type is not None:
                query = urlencode({"next_page": page_type})
                url = append_url_query_string(url, query)

            # Return error for AJAX requests with url.
            if (
                request.get_preferred_type(["application/json", "text/html"]) != "text/html"
            ):  # nocoverage
                return session_expired_ajax_response(url)

            return HttpResponseRedirect(url)

        billing_session = RemoteRealmBillingSession(
            remote_realm, remote_billing_user=remote_billing_user
        )
        return view_func(request, billing_session, *args, **kwargs)

    signature = inspect.signature(view_func)
    request_parameter, billing_session_parameter, *other_parameters = signature.parameters.values()
    _wrapped_view_func.__signature__ = signature.replace(  # type: ignore[attr-defined] # too magic
        parameters=[request_parameter, *other_parameters]
    )
    _wrapped_view_func.__annotations__ = {
        k: v for k, v in view_func.__annotations__.items() if k != billing_session_parameter.name
    }

    return _wrapped_view_func


def get_next_page_param_from_request_path(request: HttpRequest) -> str | None:
    # Our endpoint URLs in this subsystem end with something like
    # /sponsorship or /plans etc.
    # Therefore we can use this nice property to figure out easily what
    # kind of page the user is trying to access and find the right value
    # for the `next` query parameter.
    path = request.path.removesuffix("/")
    page_type = path.split("/")[-1]

    from corporate.views.remote_billing_page import (
        VALID_NEXT_PAGES as REMOTE_BILLING_VALID_NEXT_PAGES,
    )

    if page_type in REMOTE_BILLING_VALID_NEXT_PAGES:
        return page_type

    # page_type is not where we want user to go after a login, so just render the default page.
    return None  # nocoverage


def authenticated_remote_server_management_endpoint(
    view_func: Callable[
        Concatenate[HttpRequest, "RemoteServerBillingSession", ParamT], HttpResponse
    ],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        from corporate.lib.stripe import RemoteServerBillingSession

        if not is_self_hosting_management_subdomain(request):  # nocoverage
            return render(request, "404.html", status=404)

        server_uuid = kwargs.pop("server_uuid")
        if not isinstance(server_uuid, str):
            raise TypeError("server_uuid must be a string")  # nocoverage

        try:
            remote_server, remote_billing_user = get_remote_server_and_user_from_session(
                request, server_uuid=server_uuid
            )
            if remote_billing_user is None:
                # This should only be possible if the user hasn't finished the confirmation flow
                # and doesn't have a fully authenticated session yet. They should not be attempting
                # to access this endpoint yet.
                raise RemoteBillingAuthenticationError
        except (RemoteBillingIdentityExpiredError, RemoteBillingAuthenticationError):
            # In this flow, we can only redirect to our local "legacy server flow login" page.
            # That means that we can do it universally whether the user has an expired
            # identity_dict, or just lacks any form of authentication info at all - there
            # are no security concerns since this is just a local redirect.
            page_type = get_next_page_param_from_request_path(request)
            url = reverse(
                "remote_billing_legacy_server_login",
                query=None if page_type is None else {"next_page": page_type},
            )

            # Return error for AJAX requests with url.
            if (
                request.get_preferred_type(["application/json", "text/html"]) != "text/html"
            ):  # nocoverage
                return session_expired_ajax_response(url)

            return HttpResponseRedirect(url)

        assert remote_billing_user is not None
        billing_session = RemoteServerBillingSession(
            remote_server, remote_billing_user=remote_billing_user
        )
        return view_func(request, billing_session, *args, **kwargs)

    signature = inspect.signature(view_func)
    request_parameter, billing_session_parameter, *other_parameters = signature.parameters.values()
    _wrapped_view_func.__signature__ = signature.replace(  # type: ignore[attr-defined] # too magic
        parameters=[request_parameter, *other_parameters]
    )
    _wrapped_view_func.__annotations__ = {
        k: v for k, v in view_func.__annotations__.items() if k != billing_session_parameter.name
    }

    return _wrapped_view_func
