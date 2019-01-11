from django.http import HttpResponse, HttpRequest
from zerver.lib.response import json_success

# This is used only by the casper test in 00-realm-creation.js.
def confirmation_key(request: HttpRequest) -> HttpResponse:
    return json_success(request.session.get('confirmation_key'))
