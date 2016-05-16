
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
import ujson

@api_key_only_webhook_view
@has_request_variables
def api_gocd_webhook(request, user_profile, stream=REQ(default='gocd')):
    try:
        payload = ujson.loads(request.body)
    except ValueError as e:
        return json_error("Malformed JSON input, ", e.message)

    try:
        pipeline_name = payload["pipeline_name"]
        pipeline_counter = payload["pipeline_counter"]
        stage_name = payload["stage_name"]
        stage_counter = payload["stage_counter"]
        create_time = payload["create_time"]
        last_transition_time = payload["last_transition_time"]
        status = payload["status"]
        server_url = payload["server_url"]
        triggered_by = payload["triggered_by"]

    except ValueError as e:
        return json_error("Malformed JSON input, ", e.message)

    subject = '%s has %s' % (stage_name, status)

    content = 'See details: %s/%s/%s/%s/%s' % (server_url, pipeline_name, 
                            pipeline_counter, stage_name, stage_counter)


    check_send_message(user_profile, get_client('ZulipGoWebhook'), 
                            'stream', [stream], subject, content)
    return json_success()
        
    