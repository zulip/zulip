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
from django.utils.translation import gettext_lazy
from typing_extensions import override


def captcha_enabled() -> bool:
    return bool(settings.USING_CAPTCHA and settings.ALTCHA_HMAC_KEY)


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


class CaptchaFormMixin(forms.Form):
    captcha = forms.CharField(
        widget=AltchaWidget,
        error_messages={"required": gettext_lazy("Validation failed, please try again.")},
    )

    def __init__(self, *args: Any, request: HttpRequest, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.request = request
        if not captcha_enabled():
            del self.fields["captcha"]

    @override
    def clean(self) -> None:
        super().clean()
        # Validating the payload consumes the solved challenge, to
        # prevent replay; defer it until the rest of the form is
        # valid, so that a failure in some other field does not
        # invalidate a successful solve.  The captcha field does not
        # exist when the captcha is not enabled.
        if "captcha" in self.fields and not self.errors:
            try:
                validate_captcha_payload(self.request, self.cleaned_data["captcha"])
            except forms.ValidationError as error:
                self.add_error("captcha", error)


def validate_captcha_payload(request: HttpRequest, captcha_payload: str) -> None:
    if not captcha_enabled():  # nocoverage
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
