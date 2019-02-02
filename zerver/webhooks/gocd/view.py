# Webhooks for external integrations.

import json
import os

from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = (
    u'Author: {}\n'
    u'Build status: {} {}\n'
    u'Details: [build log]({})\n'
    u'Comment: {}'
)

@api_key_only_webhook_view('Gocd')
@has_request_variables
def api_gocd_webhook(request: HttpRequest, user_profile: UserProfile,
                     payload: Dict[str, Any]=REQ(argument_type='body'),
                     ) -> HttpResponse:

    modifications = payload['build_cause']['material_revisions'][0]['modifications'][0]
    result = payload['stages'][0]['result']
    material = payload['build_cause']['material_revisions'][0]['material']

    if result == "Passed":
        emoji = ':thumbs_up:'
    elif result == "Failed":
        emoji = ':thumbs_down:'

    build_details_file = os.path.join(os.path.dirname(__file__), 'fixtures/build_details.json')

    with open(build_details_file, 'r') as f:
        contents = json.load(f)
        build_link = contents["build_details"]["_links"]["pipeline"]["href"]

    body = MESSAGE_TEMPLATE.format(
        modifications['user_name'],
        result,
        emoji,
        build_link,
        modifications['comment']
    )
    branch = material['description'].split(",")
    topic = branch[0].split(" ")[1]

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
