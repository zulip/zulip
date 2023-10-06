from typing import Dict

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def config_error(request: HttpRequest, error_category_name: str) -> HttpResponse:
    contexts: Dict[str, Dict[str, object]] = {
        "apple": {"social_backend_name": "apple", "has_error_template": True},
        "google": {"social_backend_name": "google", "has_error_template": True},
        "github": {"social_backend_name": "github", "has_error_template": True},
        "gitlab": {"social_backend_name": "gitlab", "has_error_template": True},
        "ldap": {"error_name": "ldap_error_realm_is_none"},
        "dev": {"error_name": "dev_not_supported_error"},
        "saml": {"social_backend_name": "saml"},
        "smtp": {"error_name": "smtp_error"},
        "remote_user_backend_disabled": {"error_name": "remoteuser_error_backend_disabled"},
        "remote_user_header_missing": {"error_name": "remoteuser_error_remote_user_header_missing"},
        # TODO: Improve the config error page for OIDC.
        "oidc": {"error_name": "oidc_error"},
    }

    return render(request, "zerver/config_error.html", contexts[error_category_name])
