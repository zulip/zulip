from __future__ import absolute_import

from django.http import HttpResponse, HttpRequest

from typing import List
from zerver.models import UserProfile

from zerver.decorator import has_request_variables, REQ
from zerver.lib.response import json_success
from zerver.lib.validator import check_list, check_string

from zerver.lib.actions import do_add_alert_words, do_remove_alert_words, do_set_alert_words
from zerver.lib.alert_words import user_alert_words

from typing import Text

def list_alert_words(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return json_success({'alert_words': user_alert_words(user_profile)})

def clean_alert_words(alert_words):
    # type: (List[Text]) -> List[Text]
    alert_words = [w.strip() for w in alert_words]
    return [w for w in alert_words if w != ""]

@has_request_variables
def set_alert_words(request, user_profile,
                    alert_words=REQ(validator=check_list(check_string), default=[])):
    # type: (HttpRequest, UserProfile, List[Text]) -> HttpResponse
    do_set_alert_words(user_profile, clean_alert_words(alert_words))
    return json_success()

@has_request_variables
def add_alert_words(request, user_profile,
                    alert_words=REQ(validator=check_list(check_string), default=[])):
    # type: (HttpRequest, UserProfile, List[Text]) -> HttpResponse
    do_set_alert_words(user_profile, clean_alert_words(alert_words))
    return json_success()

@has_request_variables
def remove_alert_words(request, user_profile,
                       alert_words=REQ(validator=check_list(check_string), default=[])):
    # type: (HttpRequest, UserProfile, List[Text]) -> HttpResponse
    do_remove_alert_words(user_profile, alert_words)
    return json_success()
