from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import Client, UserProfile
from six import text_type
from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Optional
from six.moves import range

BODY_TEMPLATE = '''
Food nearby {displayString} coming right up:
{name_0}
{formattedAddress_0}
{descrip_0}

{name_1}
{formattedAddress_1}
{descrip_1}

{name_2}
{formattedAddress_2}
{descrip_2}'''
def get_venue_location(place):
    # type: (Dict[str, Dict[str, Any]]) -> str
    location = place['location']['formattedAddress']
    return ', '.join(location)

@api_key_only_webhook_view('FourSquare')
@has_request_variables
def api_foursquare_webhook(request, user_profile, client,
                           payload=REQ(argument_type='body'),
                           stream=REQ(default='foursquare'),
                           topic=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Dict[str, Any]], text_type, Optional[text_type]) -> HttpResponse
    try:
        search_location = payload['response']['geocode']['displayString']
        venue_list = payload['response']['groups'][0]['items']

        venue_details = {}
        for i in range(3):
            place = venue_list[i]['venue']
            venue_details['name_'+str(i)] = place['name']
            venue_details['formattedAddress_'+str(i)] = get_venue_location(place)
            venue_details['descrip_'+str(i)] = venue_list[i]['tips'][0]['text']
        venue_details['displayString'] = search_location
        body = BODY_TEMPLATE.format(**venue_details)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    if topic is None:
        topic = 'FourSquare - {displayString}'.format(displayString=search_location)

    check_send_message(user_profile, client, 'stream', [stream], topic, body)
    return json_success()
