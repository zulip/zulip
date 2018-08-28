from typing import Any, Dict

# List of StripeError's from https://stripe.com/docs/api/python#error_handling

class StripeError(Exception):
    http_status: str
    json_body: Dict[str, Any]

class CardError(StripeError):
    ...

class RateLimitError(StripeError):
    ...

class InvalidRequestError(StripeError):
    ...

class AuthenticationError(StripeError):
    ...

class APIConnectionError(StripeError):
    ...
