from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile

APPVEYOR_TOPIC_TEMPLATE = '{project_name}'
APPVEYOR_MESSAGE_TEMPLATE = ('[Build {project_name} {build_version} {status}]({build_url})\n'
                             'Commit [{commit_id}]({commit_url}) by {committer_name}'
                             ' on {commit_date}: {commit_message}\n'
                             'Build Started: {started}\n'
                             'Build Finished: {finished}')

@api_key_only_webhook_view('Appveyor')
@has_request_variables
def api_appveyor_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    event_data = payload['eventData']
    return APPVEYOR_TOPIC_TEMPLATE.format(project_name=event_data['projectName'])

def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    event_data = payload['eventData']

    data = {
        "project_name": event_data['projectName'],
        "build_version": event_data['buildVersion'],
        "status": event_data['status'],
        "build_url": event_data['buildUrl'],
        "commit_url": event_data['commitUrl'],
        "committer_name": event_data['committerName'],
        "commit_date": event_data['commitDate'],
        "commit_message": event_data['commitMessage'],
        "commit_id": event_data['commitId'],
        "started": event_data['started'],
        "finished": event_data['finished']
    }
    return APPVEYOR_MESSAGE_TEMPLATE.format(**data)
