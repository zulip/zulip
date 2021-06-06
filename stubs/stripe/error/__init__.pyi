from typing import Any, Dict, Optional

# List of StripeError's from https://stripe.com/docs/api/python#error_handling
# and https://github.com/stripe/stripe-python/blob/master/stripe/error.py

class StripeError(Exception):
    def __init__(self, message: Optional[str]=None, http_body: Optional[str]=None,
                 http_status: Optional[int]=None, json_body: Optional[Dict[str, Any]]=None,
                 headers: Optional[Dict[str, Any]]=None, code: Optional[str]=None) -> None:
        ...

    http_status: str
    json_body: Dict[str, Any]

class CardError(StripeError):
    def __init__(self, message: str, param: str, code: str, http_body: Optional[str]=None,
                 http_status: Optional[int]=None, json_body: Optional[Dict[str, Any]]=None,
                 headers: Optional[Dict[str, Any]]=None) -> None:
        ...

class RateLimitError(StripeError):
    ...

class InvalidRequestError(StripeError):
    def __init__(self, message: str, param: str, code: str, http_body: Optional[str]=None,
                 http_status: Optional[int]=None, json_body: Optional[Dict[str, Any]]=None,
                 headers: Optional[Dict[str, Any]]=None) -> None:
        ...

class AuthenticationError(StripeError):
    ...

class APIConnectionError(StripeError):
    def __init__(self, message: Optional[str]=None, http_body: Optional[str]=None,
                 http_status: Optional[int]=None, json_body: Optional[Dict[str, Any]]=None,
                 headers: Optional[Dict[str, Any]]=None, code: Optional[str]=None,
                 should_retry: bool=False) -> None:
        ...
