# Webhooks for teamcity integration
from __future__ import absolute_import

from django.db.models import Q
from typing import Optional

from zerver.models import UserProfile, Realm
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view


import logging
import ujson

def guess_zulip_user_from_teamcity(teamcity_username, realm):
    # type: (str, Realm) -> Optional[UserProfile]
    try:
        # Try to find a matching user in Zulip
        # We search a user's full name, short name,
        # and beginning of email address
        user = UserProfile.objects.filter(
                Q(full_name__iexact=teamcity_username) |
                Q(short_name__iexact=teamcity_username) |
                Q(email__istartswith=teamcity_username),
                is_active=True,
                realm=realm).order_by("id")[0]
        return user
    except IndexError:
        return None

def get_teamcity_property_value(property_list, name):
    # type: (List[Dict[str, str]], str) -> Optional[str]
    for property in property_list:
        if property['name'] == name:
            return property['value']
    return None

@api_key_only_webhook_view('Teamcity')
@has_request_variables
def api_teamcity_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                         stream=REQ(default='teamcity')):
    # (HttpRequest, UserProfile, Client, Dict[str, Any], str) -> HttpResponse
    message = payload['build']

    build_name = message['buildFullName']
    build_url = message['buildStatusUrl']
    changes_url = build_url + '&tab=buildChangesDiv'
    build_number = message['buildNumber']
    build_result = message['buildResult']
    build_result_delta = message['buildResultDelta']
    build_status = message['buildStatus']

    if build_result == 'success':
        if build_result_delta == 'fixed':
            status = 'has been fixed! :thumbsup:'
        else:
            status = 'was successful! :thumbsup:'
    elif build_result == 'failure':
        if build_result_delta == 'broken':
            status = 'is broken with status %s! :thumbsdown:' % (build_status)
        else:
            status = 'is still broken with status %s! :thumbsdown:' % (build_status)
    elif build_result == 'running':
        status = 'has started.'
    else:
        status = '(has no message specified for status %s)' % (build_status)

    template = (
        u'%s build %s %s\n'
        u'Details: [changes](%s), [build log](%s)')

    body = template % (build_name, build_number, status, changes_url, build_url)
    topic = build_name

    # Check if this is a personal build, and if so try to private message the user who triggered it.
    if get_teamcity_property_value(message['teamcityProperties'], 'env.BUILD_IS_PERSONAL') == 'true':
        # The triggeredBy field gives us the teamcity user full name, and the "teamcity.build.triggeredBy.username"
        # property gives us the teamcity username. Let's try finding the user email from both.
        teamcity_fullname = message['triggeredBy'].split(';')[0]
        teamcity_user = guess_zulip_user_from_teamcity(teamcity_fullname, user_profile.realm)

        if teamcity_user is None:
            teamcity_shortname = get_teamcity_property_value(message['teamcityProperties'],
                                                             'teamcity.build.triggeredBy.username')
            if teamcity_shortname is not None:
                teamcity_user = guess_zulip_user_from_teamcity(teamcity_shortname, user_profile.realm)

        if teamcity_user is None:
            # We can't figure out who started this build - there's nothing we can do here.
            logging.info("Teamcity webhook couldn't find a matching Zulip user for Teamcity user '%s' or '%s'" % (
                teamcity_fullname, teamcity_shortname))
            return json_success()

        body = "Your personal build of " + body
        check_send_message(user_profile, client, 'private', [teamcity_user.email], topic, body)
        return json_success()

    check_send_message(user_profile, client, 'stream', [stream], topic, body)
    return json_success()
