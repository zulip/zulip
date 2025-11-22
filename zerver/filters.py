import re
from typing import Any

from django.http import HttpRequest
from django.views.debug import SafeExceptionReporterFilter
from typing_extensions import override


class ZulipExceptionReporterFilter(SafeExceptionReporterFilter):
    # Add _SALT to the standard list
    hidden_settings = re.compile(
        r"API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|_SALT", flags=re.IGNORECASE
    )

    @override
    def get_post_parameters(self, request: HttpRequest | None) -> dict[str, Any]:
        post_data = super().get_post_parameters(request)

        filtered_post = post_data.copy()
        filtered_vars = [
            "content",
            "secret",
            "password",
            "key",
            "api-key",
            "subject",
            "stream",
            "subscriptions",
            "to",
            "csrfmiddlewaretoken",
            "api_key",
            "realm_counts",
            "installation_counts",
        ]

        for var in filtered_vars:
            if var in filtered_post:
                filtered_post[var] = "**********"
        return filtered_post

    @override
    def get_safe_settings(self) -> dict[str, Any]:
        return {}
