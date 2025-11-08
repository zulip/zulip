from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def config_error(
    request: HttpRequest,
    error_name: str,
    *,
    go_back_to_url: str | None = None,
    go_back_to_url_name: str | None = None,
) -> HttpResponse:
    assert "/" not in error_name
    context = {
        "error_name": error_name,
        "go_back_to_url": go_back_to_url or "/login/",
        "go_back_to_url_name": go_back_to_url_name or "the login page",
    }
    if settings.DEVELOPMENT:
        context["auth_settings_path"] = "zproject/dev-secrets.conf"
        context["client_id_key_name"] = f"social_auth_{error_name}_key"
    else:
        context["auth_settings_path"] = "/etc/zulip/settings.py"
        context["client_id_key_name"] = f"SOCIAL_AUTH_{error_name.upper()}_KEY"

    return render(request, f"zerver/config_error/{error_name}.html", context=context, status=500)
