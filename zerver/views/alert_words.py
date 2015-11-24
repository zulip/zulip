from __future__ import absolute_import

from django.views.decorators.csrf import csrf_exempt

from zerver.decorator import authenticated_json_post_view, has_request_variables, REQ
from zerver.lib.response import json_success
from zerver.lib.validator import check_list, check_string

from zerver.lib.actions import do_add_alert_words, do_remove_alert_words, do_set_alert_words
from zerver.lib.alert_words import user_alert_words

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

def list_alert_words(request, user_profile):
    return json_success({'alert_words': user_alert_words(user_profile)})

@authenticated_json_post_view
@has_request_variables
def json_set_alert_words(request, user_profile,
                         alert_words=REQ(validator=check_list(check_string), default=[])):
    do_set_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def set_alert_words(request, user_profile,
                    alert_words=REQ(validator=check_list(check_string), default=[])):
    do_set_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def add_alert_words(request, user_profile,
                    alert_words=REQ(validator=check_list(check_string), default=[])):
    do_add_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def remove_alert_words(request, user_profile,
                       alert_words=REQ(validator=check_list(check_string), default=[])):
    do_remove_alert_words(user_profile, alert_words)
    return json_success()
