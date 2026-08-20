import base64
import logging
from typing import Any

import orjson
from altcha.v1 import verify_solution
from django import forms
from django.conf import settings
from django.forms.renderers import BaseRenderer
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.translation import gettext as _
from typing_extensions import override


class AltchaWidget(forms.TextInput):
    @override
    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: BaseRenderer | None = None,
    ) -> SafeString:
        return format_html(
            (
                "<altcha-widget"
                '  name="captcha"'
                '  challengeurl="/json/antispam_challenge"'
                "  hidelogo"
                "  hidefooter"
                "  refetchonexpire"
                '  style="{}"'
                '  strings="{}"'
                ">"
            ),
            "--altcha-max-width: 300px;",
            orjson.dumps(
                {
                    "verified": _("Verified that you're a human user!"),
                    "verifying": _("Verifying that you're not a bot…"),
                }
            ).decode(),
        )


def validate_captcha_payload(request: HttpRequest, captcha_payload: str) -> None:
    if not settings.USING_CAPTCHA or not settings.ALTCHA_HMAC_KEY:  # nocoverage
        raise forms.ValidationError(_("Challenges are not enabled."))

    try:
        ok, err = verify_solution(captcha_payload, settings.ALTCHA_HMAC_KEY, check_expires=True)
        if not ok:
            logging.warning("Invalid altcha solution: %s", err)
            raise forms.ValidationError(_("Validation failed, please try again."))
    except forms.ValidationError:
        raise
    except Exception:
        logging.exception("Error while validating altcha solution")
        raise forms.ValidationError(_("Validation failed, please try again."))

    captcha_data = orjson.loads(base64.b64decode(captcha_payload))
    challenge = captcha_data["challenge"]
    session_challenges = [e[0] for e in request.session.get("altcha_challenges", [])]
    if challenge not in session_challenges:
        logging.warning("Expired or replayed altcha solution")
        raise forms.ValidationError(_("Validation failed, please try again."))

    # Remove the successful solve from the session, to prevent replay
    request.session["altcha_challenges"] = [
        e for e in request.session.get("altcha_challenges", []) if e[0] != challenge
    ]
