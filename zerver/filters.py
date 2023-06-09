from typing import Any, Dict, Optional

from django.http import HttpRequest
from django.views.debug import SafeExceptionReporterFilter


class ZulipExceptionReporterFilter(SafeExceptionReporterFilter):
    def get_post_parameters(self, request: Optional[HttpRequest]) -> Dict[str, Any]:
        post_data = SafeExceptionReporterFilter.get_post_parameters(self, request)
        assert isinstance(post_data, dict)
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
