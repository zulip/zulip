import logging
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
    now = timezone_now()
    expires = now + timedelta(minutes=1)
    try:
        challenge = create_challenge(
            ChallengeOptions(
                hmac_key=settings.ALTCHA_HMAC_KEY,
                max_number=500000,
                expires=expires,
            )
        )
        session_challenges = request.session.get("altcha_challenges", [])
        # We prune out expired challenges not for correctness (the
        # expiration is validated separately) but to prevent this from
        # growing without bound
        session_challenges = [(c, e) for (c, e) in session_challenges if e > now.timestamp()]
        request.session["altcha_challenges"] = [
            *session_challenges,
            (challenge.challenge, expires.timestamp()),
        ]
        return json_success(request, data=challenge.__dict__)
    except Exception as e:  # nocoverage
        logging.exception(e)
        raise JsonableError(_("Failed to generate challenge"))
