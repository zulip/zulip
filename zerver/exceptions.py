from __future__ import absolute_import

from django.core.exceptions import PermissionDenied

class RateLimited(PermissionDenied):
    def __init__(self, msg=""):
        # type: (str) -> None
        super(RateLimited, self).__init__(msg)
