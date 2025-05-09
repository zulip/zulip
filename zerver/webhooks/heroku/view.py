from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ADDON_ATTACH_TEMPLATE = """
{resource_label}: **{name}** was {action} by **{actor}**:
* Addon: **{addon_name}**
"""

ADDON_TEMPLATE = """
{resource_label}: **{name}** was {action} by **{actor}**:
* Service: {service}
* Plan: {plan}
"""

APP_TEMPLATE = """
{resource_label}: **{name}** was {action} by **{actor}**:
* Build Stack: {build_stack}
* Region: {region}{organization}
* Git URL: {git_url}
"""

BUILD_TEMPLATE = """
{resource_label} was {action} by **{actor}**:
* Status: {status}
* Build Stack: {build_stack}
"""

COLLAB_TEMPLATE = "{resource_label}: **{email}** was {action} by **{actor}**{role}"

DOMAIN_TEMPLATE = """
{resource_label} was {action} by **{actor}**:
* Hostname: {hostname}
* Kind: {kind}
* Status: {status}
"""

DYNO_TEMPLATE = """
{resource_label}: **{name}** was {action} by **{actor}**:
* Size: {size}
* Type: {type}
* State: {state}
"""

FORMATION_TEMPLATE = """
{resource_label} was {action} by **{actor}**:
* Command: {command}
* Size: {size}
* Type: {type}
* Quantity: {quantity}
"""

RELEASE_TEMPLATE = """
{resource_label} was {action} by **{actor}**:{current}
* Status: {status}
* Version: {version}{description}
"""

SNI_ENDPOINT_TEMPLATE = "{resource_label}: **{name}** was {action} by **{actor}**."

ALL_EVENT_TYPES: list[str] = [
    "addon-attachment",
    "addon",
    "app",
    "build",
    "collaborator",
    "domain",
    "dyno",
    "formation",
    "release",
    "sni-endpoint",
]


def format_resource_label(resource: str, action: str) -> str:
    if action == "create":
        return f"A new {resource}"
    elif resource in ["addon attachment", "addon", "app"]:
        return f"An {resource}"
    return f"A {resource}"


@webhook_view("Heroku", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_heroku_webhook(
    request: HttpRequest, user_profile: UserProfile, *, payload: JsonBodyPayload[WildValue]
) -> HttpResponse:
    action: str = payload["action"].tame(check_string)
    resource: str = payload["resource"].tame(check_string)
    actor: str = payload["actor"]["email"].tame(check_string)

    formatted_action: str = action + "ed" if action == "destroy" else action + "d"
    topic: str = (  # Heroku App name
        payload["data"]["app"]["name"].tame(check_string)
        if resource != "app"
        else payload["data"]["name"].tame(check_string)
    )
    message: str

    match resource:
        case "addon-attachment":
            web_url = payload["data"].get("web_url")
            formatted_name = payload["data"]["name"].tame(check_string)
            if web_url:
                formatted_name = f"[{formatted_name}]({web_url.tame(check_string)})"

            message = ADDON_ATTACH_TEMPLATE.format(
                resource_label=format_resource_label("addon attachment", action),
                action=formatted_action,
                actor=actor,
                name=formatted_name,
                addon_name=payload["data"]["addon"]["name"].tame(check_string),
            )
        case "addon":
            web_url = payload["data"].get("web_url")
            formatted_name = payload["data"]["name"].tame(check_string)
            if web_url:
                formatted_name = f"[{formatted_name}]({web_url.tame(check_string)})"

            message = ADDON_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                name=formatted_name,
                actor=actor,
                service=payload["data"]["addon_service"]["name"].tame(check_string),
                plan=payload["data"]["plan"]["name"].tame(check_string),
            )
        case "app":
            web_url = payload["data"].get("web_url")
            organization = payload["data"].get("organization")
            formatted_name = payload["data"]["name"].tame(check_string)
            organization_message = ""
            if web_url:
                formatted_name = f"[{formatted_name}]({web_url.tame(check_string)})"
            if organization:
                organization_message = (
                    f"\n* Organization: {organization['name'].tame(check_string)}"
                )

            message = APP_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                name=(
                    f"[{payload['data']['name'].tame(check_string)}]({web_url.tame(check_string)})"
                    if web_url
                    else payload["data"]["name"].tame(check_string)
                ),
                actor=actor,
                build_stack=payload["data"]["build_stack"]["name"].tame(check_string),
                region=payload["data"]["region"]["name"].tame(check_string),
                organization=organization_message,
                git_url=payload["data"]["git_url"].tame(check_string),
            )
        case "build":
            message = BUILD_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                actor=actor,
                status=payload["data"]["status"].tame(check_string),
                build_stack=payload["data"]["stack"].tame(check_string),
            )
        case "collaborator":
            role = payload["data"].get("role")
            role_message = ""
            if role:
                role_message = f":\n* Role: {role.tame(check_string)}"

            message = COLLAB_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                actor=actor,
                email=payload["data"]["user"]["email"].tame(check_string),
                role=role_message,
            )
        case "domain":
            message = DOMAIN_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                actor=actor,
                hostname=payload["data"]["hostname"].tame(check_string),
                kind=payload["data"]["kind"].tame(check_string),
                status=payload["data"]["status"].tame(check_string),
            )
        case "dyno":
            message = DYNO_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                name=payload["data"]["name"].tame(check_string),
                actor=actor,
                size=payload["data"]["size"].tame(check_string),
                type=payload["data"]["type"].tame(check_string),
                state=payload["data"]["state"].tame(check_string),
            )
        case "formation":
            message = FORMATION_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                actor=actor,
                command=payload["data"]["command"].tame(check_string),
                size=payload["data"]["size"].tame(check_string),
                type=payload["data"]["type"].tame(check_string),
                quantity=payload["data"]["quantity"].tame(check_int),
            )
        case "release":
            current = payload["data"].get("current")
            description = payload["data"].get("description")
            current_message = ""
            description_message = ""
            if current:
                current_message = f"\n* Current: {current.tame(check_bool)}"
            if description:
                description_message = f"\n* Description: {description.tame(check_string)}"

            message = RELEASE_TEMPLATE.format(
                resource_label=format_resource_label(resource, action),
                action=formatted_action,
                actor=actor,
                status=payload["data"]["status"].tame(check_string),
                current=current_message,
                version=payload["data"]["version"].tame(check_int),
                description=description_message,
            )
        case "sni-endpoint":
            message = SNI_ENDPOINT_TEMPLATE.format(
                resource_label=format_resource_label("SNI endpoint", action),
                action=formatted_action,
                name=payload["data"]["name"].tame(check_string),
                actor=actor,
            )
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
