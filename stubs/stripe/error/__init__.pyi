class StripeError(Exception):
    http_status: str

class CardError(Exception):
    http_status: str

class InvalidRequestError(Exception):
    ...
