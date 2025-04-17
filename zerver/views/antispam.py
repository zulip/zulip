from datetime import timedelta

from altcha import ChallengeOptions, create_challenge
from django.conf import settings
from django.http import HttpRequest, HttpResponseBase
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import BaseModel

from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters


class AltchaPayload(BaseModel):
    algorithm: str
    challenge: str
    number: int
    salt: str
    signature: str


@typed_endpoint_without_parameters
def get_challenge(
    request: HttpRequest,
) -> HttpResponseBase:
    try:
        challenge = create_challenge(
            ChallengeOptions(
                hmac_key=settings.ALTCHA_HMAC_KEY,
                max_number=50000,
                expires=timezone_now() + timedelta(minutes=10),
            )
        )
        request.session["altcha_challenges"] = [
            *request.session.get("altcha_challenges", []),
            challenge.challenge,
        ]
        return json_success(request, data=challenge.__dict__)
    except Exception:
        raise JsonableError(_("Failed to generate challenge"))
