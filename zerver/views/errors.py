from typing import Dict

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def config_error(request: HttpRequest, error_category_name: str) -> HttpResponse:
    contexts: Dict[str, Dict[str, object]] = {
        "apple": {"social_backend_name": "apple", "has_error_template": True},
        "google": {"social_backend_name": "google", "has_error_template": True},
        "github": {"social_backend_name": "github", "has_error_template": True},
        "gitlab": {"social_backend_name": "gitlab", "has_error_template": True},
    }

    context = contexts.get(error_category_name, {})
    context["error_name"] = error_category_name
    return render(request, "zerver/config_error.html", context)
