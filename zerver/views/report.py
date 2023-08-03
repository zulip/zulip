# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html
import logging

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value


@csrf_exempt
@require_POST
@has_request_variables
def report_csp_violations(
    request: HttpRequest,
    csp_report: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    def get_attr(csp_report_attr: str) -> str:
        return csp_report.get(csp_report_attr, "").tame(check_string)

    logging.warning(
        "CSP violation in document('%s'). "
        "blocked URI('%s'), original policy('%s'), "
        "violated directive('%s'), effective directive('%s'), "
        "disposition('%s'), referrer('%s'), "
        "status code('%s'), script sample('%s')",
        get_attr("document-uri"),
        get_attr("blocked-uri"),
        get_attr("original-policy"),
        get_attr("violated-directive"),
        get_attr("effective-directive"),
        get_attr("disposition"),
        get_attr("referrer"),
        get_attr("status-code"),
        get_attr("script-sample"),
    )

    return json_success(request)
