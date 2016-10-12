from __future__ import absolute_import

from typing import Any

from django.views.debug import SafeExceptionReporterFilter
from django.http import HttpRequest, build_request_repr

class ZulipExceptionReporterFilter(SafeExceptionReporterFilter):
    def get_post_parameters(self, request):
        # type: (HttpRequest) -> Dict[str, Any]
        filtered_post = SafeExceptionReporterFilter.get_post_parameters(self, request).copy()
        filtered_vars = ['content', 'secret', 'password', 'key', 'api-key', 'subject', 'stream',
                         'subscriptions', 'to', 'csrfmiddlewaretoken', 'api_key']

        for var in filtered_vars:
            if var in filtered_post:
                filtered_post[var] = '**********'
        return filtered_post
    def get_request_repr(self, request):
        # type: (HttpRequest) -> str
        if request is None:
            return repr(None)
        else:
            return build_request_repr(request,
                                      POST_override=self.get_post_parameters(request),
                                      COOKIES_override="**********",
                                      META_override="**********")
