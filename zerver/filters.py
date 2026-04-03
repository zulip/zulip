import re
from typing import Any

from django.conf import settings
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

    # We do not include Django settings in exception reports at all.
    # Settings can contain secrets and other environment-specific
    # details, and we rely on other mechanisms to inspect them when
    # debugging. Returning an empty dict here tells ExceptionReporter
    # to omit settings-related context entirely.
    @override
    def get_safe_settings(self) -> dict[str, Any]:
        # In production, we do not include Django settings in exception reports at all.
        # Settings can contain secrets and other environment-specific
        # details.
        if settings.PRODUCTION:
            return {}

        # In development, return the safe settings (secrets masked by hidden_settings regex)
        return super().get_safe_settings()
