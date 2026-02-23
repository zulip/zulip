import logging

import jwt
from django.conf import settings

logger = logging.getLogger(__name__)


class JWTValidationError(Exception):
    """Raised when JWT validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_supabase_jwt(token: str) -> dict:
    """Validate a Supabase JWT token and return the decoded payload.

    Args:
        token: The raw JWT string (without "Bearer " prefix).

    Returns:
        Decoded JWT payload dict containing sub, email, phone, etc.

    Raises:
        JWTValidationError: If the token is invalid, expired, or missing required claims.
    """
    secret = getattr(settings, "NODL_SUPABASE_JWT_SECRET", "") or getattr(
        settings, "SUPABASE_JWT_SECRET", ""
    )
    if not secret:
        logger.error("NODL_SUPABASE_JWT_SECRET is not configured")
        raise JWTValidationError("Server configuration error")

    supabase_url = getattr(settings, "NODL_SUPABASE_URL", "")

    try:
        decode_options = {}
        if supabase_url:
            issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        else:
            # Skip issuer validation if NODL_SUPABASE_URL not set
            decode_options["verify_iss"] = False
            issuer = None

        kwargs: dict = {
            "algorithms": ["HS256"],
            "audience": "authenticated",
            "options": decode_options,
        }
        if issuer:
            kwargs["issuer"] = issuer

        payload = jwt.decode(token, secret, **kwargs)

    except jwt.ExpiredSignatureError as e:
        raise JWTValidationError("Token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise JWTValidationError("Invalid audience claim") from e
    except jwt.InvalidIssuerError as e:
        raise JWTValidationError("Invalid issuer claim") from e
    except jwt.InvalidTokenError as e:
        raise JWTValidationError(f"Invalid JWT token: {e}") from e

    # Validate required claims
    if "sub" not in payload:
        raise JWTValidationError("Missing 'sub' claim")

    return payload
