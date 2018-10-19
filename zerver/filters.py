
import re
from typing import Any, Dict

from django.http import HttpRequest
from django.views.debug import SafeExceptionReporterFilter

class ZulipExceptionReporterFilter(SafeExceptionReporterFilter):
    def get_post_parameters(self, request: HttpRequest) -> Dict[str, Any]:
        filtered_post = SafeExceptionReporterFilter.get_post_parameters(self, request).copy()
        filtered_vars = ['content', 'secret', 'password', 'key', 'api-key', 'subject', 'stream',
                         'subscriptions', 'to', 'csrfmiddlewaretoken', 'api_key']

        for var in filtered_vars:
            if var in filtered_post:
                filtered_post[var] = '**********'
        return filtered_post

def clean_data_from_query_parameters(val: str) -> str:
    return re.sub(r"([a-z_-]+=)([^&]+)([&]|$)", r"\1******\3", val)
