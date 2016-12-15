from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Dict, Any, Iterable, Optional

@api_key_only_webhook_view('FourSquare')
@has_request_variables
def api_foursquare_webhook(request, user_profile, client,
                            payload=REQ(argument_type='body'),
                            stream=REQ(default='test'),
                            topic=REQ(default='FourSquare')):
                                # type: (HttpRequest, UserProfile, Client, Dict[str, Iterable[Dict[str, Any]]], text_type, Optional[text_type]) -> HttpResponse

    # construct the body/ start of the message
    body = 'Food nearby '

    # try to add the Foursquare results
    # return appropriate error if not successful
    try:
        # JSON list of venues
        venue_list = payload['response']['groups'][0]['items']

        # seperation into 3 venues and defines location
        place1 = venue_list[0]['venue']
        location1 = place1['location']['formattedAddress']
        fulladdress1 = location1[0] + ', ' + location1[1] + ', ' + location1[2]

        place2 = venue_list[1]['venue']
        location2 = place2['location']['formattedAddress']
        fulladdress2 = location2[0] + ', ' + location2[1] + ', ' + location2[2]

        place3 = venue_list[2]['venue']
        location3 = place3['location']['formattedAddress']
        fulladdress3 = location3[0] + ', ' + location3[1] + ', ' + location3[2]

        body_template = ("{displayString} coming right up\n\n {name1}\n{formattedAddress1}\n{text1}\n\n"
                        +"{name2}\n{formattedAddress2}\n{text2}\n\n {name3}\n{formattedAddress3}\n{text3}")

        body += body_template.format(displayString=payload['response']['geocode']['displayString'],
                                    name1=place1['name'], formattedAddress1=fulladdress1, text1=venue_list[0]['tips'][0]['text'],
                                    name2=place2['name'], formattedAddress2=fulladdress2, text2=venue_list[1]['tips'][0]['text'],
                                    name3=place3['name'], formattedAddress3=fulladdress3, text3=venue_list[2]['tips'][0]['text'])

    except KeyError as e:

        return json_error(_("Missing key {} in JSON").format(str(e)))

    # send the message
    check_send_message(user_profile, client, 'stream', [stream], topic, body)

    # return json result
    return json_success()
