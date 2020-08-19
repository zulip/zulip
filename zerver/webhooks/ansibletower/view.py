import operator
from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables, webhook_view
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ANSIBLETOWER_DEFAULT_MESSAGE_TEMPLATE = "{friendly_name}: [#{id} {name}]({url}) {status}."


ANSIBLETOWER_JOB_MESSAGE_TEMPLATE = """
{friendly_name}: [#{id} {name}]({url}) {status}:
{hosts_final_data}
""".strip()

ANSIBLETOWER_JOB_HOST_ROW_TEMPLATE = '* {hostname}: {status}\n'

@webhook_view('Ansibletower')
@has_request_variables
def api_ansibletower_webhook(request: HttpRequest, user_profile: UserProfile,
                             payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    body = get_body(payload)
    subject = payload['name']

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def extract_friendly_name(payload: Dict[str, Any]) -> str:
    tentative_job_name = payload.get("friendly_name", "")
    if not tentative_job_name:
        url = payload["url"]
        segments = url.split("/")
        tentative_job_name = segments[-3]
        if tentative_job_name == "jobs":
            tentative_job_name = "Job"
    return tentative_job_name

def get_body(payload: Dict[str, Any]) -> str:
    friendly_name = extract_friendly_name(payload)
    if (friendly_name == 'Job'):
        hosts_list_data = payload['hosts']
        hosts_data = []
        for host in payload['hosts']:
            if (hosts_list_data[host].get('failed') is True):
                hoststatus = 'Failed'
            elif (hosts_list_data[host].get('failed') is False):
                hoststatus = 'Success'
            hosts_data.append({
                'hostname': host,
                'status': hoststatus,
            })

        if (payload['status'] == "successful"):
            status = 'was successful'
        else:
            status = 'failed'

        return ANSIBLETOWER_JOB_MESSAGE_TEMPLATE.format(
            name=payload['name'],
            friendly_name=friendly_name,
            id=payload['id'],
            url=payload['url'],
            status=status,
            hosts_final_data=get_hosts_content(hosts_data),
        )

    else:

        if (payload['status'] == "successful"):
            status = 'was successful'
        else:
            status = 'failed'

        data = {
            "name": payload['name'],
            "friendly_name": friendly_name,
            "id": payload['id'],
            "url": payload['url'],
            "status": status,
        }

        return ANSIBLETOWER_DEFAULT_MESSAGE_TEMPLATE.format(**data)

def get_hosts_content(hosts_data: List[Dict[str, Any]]) -> str:
    hosts_data = sorted(hosts_data, key=operator.itemgetter('hostname'))
    hosts_content = ''
    for host in hosts_data:
        hosts_content += ANSIBLETOWER_JOB_HOST_ROW_TEMPLATE.format(
            hostname=host.get('hostname'),
            status=host.get('status'),
        )
    return hosts_content
