from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.forms.models import modelform_factory
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import path
from django.utils.translation import gettext as _
from oauth2_provider.models import get_application_model
from oauth2_provider.views import (
    ApplicationDelete,
    ApplicationDetail,
    ApplicationList,
    ApplicationRegistration,
    ApplicationUpdate,
    AuthorizationView,
    RevokeTokenView,
    TokenView,
)
from typing_extensions import ParamSpec, override

from zerver.decorator import zulip_login_required
from zerver.models import UserProfile

ParamT = ParamSpec("ParamT")

# Fields shown on the stock django-oauth-toolkit application create/edit forms.
APPLICATION_FORM_FIELDS = (
    "name",
    "client_id",
    "client_secret",
    "client_type",
    "authorization_grant_type",
    "redirect_uris",
)


class ZulipOAuthApplicationForm(forms.ModelForm[models.Model]):
    """Application form with grant type fixed to authorization code.

    The field is shown disabled so users cannot pick another OAuth grant
    type. Django ignores client-submitted values for disabled fields and
    uses the form initial value instead.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        Application = get_application_model()
        grant_field = self.fields["authorization_grant_type"]
        assert isinstance(grant_field, forms.ChoiceField)
        grant_field.choices = [
            (Application.GRANT_AUTHORIZATION_CODE, _("Authorization code")),
        ]
        grant_field.disabled = True
        grant_field.initial = Application.GRANT_AUTHORIZATION_CODE
        self.initial.setdefault("authorization_grant_type", Application.GRANT_AUTHORIZATION_CODE)


def get_zulip_application_form_class() -> type[forms.ModelForm[models.Model]]:
    return modelform_factory(
        get_application_model(),
        form=ZulipOAuthApplicationForm,
        fields=APPLICATION_FORM_FIELDS,
    )


def require_oauth_application_admin(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @zulip_login_required
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        user_profile = request.user
        assert isinstance(user_profile, UserProfile)
        if not user_profile.is_realm_admin:
            return render(request, "404.html", status=404)
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


class ZulipApplicationRegistration(ApplicationRegistration):
    @override
    def get_form_class(self) -> type[forms.ModelForm[models.Model]]:
        return get_zulip_application_form_class()


class ZulipApplicationUpdate(ApplicationUpdate):
    @override
    def get_form_class(self) -> type[forms.ModelForm[models.Model]]:
        return get_zulip_application_form_class()


class ZulipAuthorizationView(AuthorizationView):
    @override
    def handle_no_permission(self) -> HttpResponse:
        # DOT redirects prompt=none to the raw redirect_uri without
        # checking a registered client. We are not an OIDC provider.
        return LoginRequiredMixin.handle_no_permission(self)


# The access token validation happens in zerver.decorator.authenticated_rest_api_view
# and in zerver.views.tusd.authenticate_user.
# The oauth2_provider package from django-oauth-toolkit supplies the database models,
# migrations, and OAuth2 views out of the box.
oauth2_endpoint_views = [
    # OAuth2 Application Management endpoints
    path("applications/", require_oauth_application_admin(ApplicationList.as_view()), name="list"),
    path(
        "applications/register/",
        require_oauth_application_admin(ZulipApplicationRegistration.as_view()),
        name="register",
    ),
    path(
        "applications/<pk>/",
        require_oauth_application_admin(ApplicationDetail.as_view()),
        name="detail",
    ),
    path(
        "applications/<pk>/delete/",
        require_oauth_application_admin(ApplicationDelete.as_view()),
        name="delete",
    ),
    path(
        "applications/<pk>/update/",
        require_oauth_application_admin(ZulipApplicationUpdate.as_view()),
        name="update",
    ),
    # tokens
    path(
        "authorize/",
        zulip_login_required(ZulipAuthorizationView.as_view()),
        name="authorize",
    ),
    path("token/", TokenView.as_view(), name="token"),
    path("revoke-token/", RevokeTokenView.as_view(), name="revoke-token"),
]
