from __future__ import absolute_import
from typing import Text

from django.core.exceptions import PermissionDenied

class JsonableError(Exception):
    msg = None  # type: Text
    status_code = None  # type: int

    def __init__(self, msg, status_code=400):
        # type: (Text) -> None
        self.msg = msg
        self.status_code = status_code

    def __str__(self):
        # type: () -> str
        return self.to_json_error_msg()  # type: ignore # remove once py3-only

    def to_json_error_msg(self):
        # type: () -> Text
        return self.msg

class RateLimited(PermissionDenied):
    def __init__(self, msg=""):
        # type: (str) -> None
        super(RateLimited, self).__init__(msg)
