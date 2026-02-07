"""
CSP violation report endpoint.

Receives POST requests from browsers when Content-Security-Policy-Report-Only
violations occur. Logs reports for analysis; does not block or authenticate.
Issue: https://github.com/zulip/zulip/issues/11835
"""

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger("zulip.csp_violations")


@csrf_exempt
@require_POST
def csp_violations(request: HttpRequest) -> HttpResponse:
    """
    Accept CSP violation reports from browsers.

    Browsers POST application/csp-report or application/json with body:
    {"csp-report": {"document-uri": "...", "blocked-uri": "...", ...}}
    """
    try:
        body = request.body.decode("utf-8")
        data: dict[str, Any] = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.warning("CSP violation report invalid JSON or encoding: %s", e)
        return HttpResponse(status=204)

    report = data.get("csp-report")
    if not isinstance(report, dict):
        logger.warning("CSP violation report missing or invalid 'csp-report' key")
        return HttpResponse(status=204)

    logger.info(
        "CSP violation: directive=%s blocked=%s document=%s",
        report.get("violated-directive", report.get("effective-directive", "?")),
        report.get("blocked-uri", "?"),
        report.get("document-uri", "?"),
    )
    return HttpResponse(status=204)
