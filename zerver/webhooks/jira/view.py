# Webhooks for external integrations.
import re
import string
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import (
    AnomalousWebhookPayloadError,
    JsonableError,
    UnsupportedWebhookEventTypeError,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import Realm, UserProfile
from zerver.models.users import get_user_by_delivery_email

IGNORED_EVENTS = [
    "attachment_created",
    "issuelink_created",
    "issuelink_deleted",
    "jira:version_released",
    "jira:worklog_updated",
    "sprint_closed",
    "sprint_started",
    "worklog_created",
    "worklog_updated",
]

MAX_LENGTH = 15


@dataclass
class Auth:
    email: str
    jira_api_token: str


def guess_zulip_user_from_jira(jira_username: str, realm: Realm) -> UserProfile | None:
    try:
        # Try to find a matching user in Zulip
        # We search a user's full name, short name,
        # and beginning of email address
        user = UserProfile.objects.filter(
            Q(full_name__iexact=jira_username) | Q(email__istartswith=jira_username),
            is_active=True,
            realm=realm,
        ).order_by("id")[0]
        return user
    except IndexError:
        return None


def convert_jira_markup(payload: WildValue, realm: Realm, auth: Auth | None) -> str:
    # Attempt to do some simplistic conversion of Jira
    # formatting to Markdown, for consumption in Zulip

    content = get_in(payload, ["comment", "body"]).tame(check_string)

    # Jira uses *word* for bold, we use **word**
    content = re.sub(r"\*([^\*]+)\*", r"**\1**", content)

    # Jira uses {{word}} for monospacing, we use `word`
    content = re.sub(r"{{([^\*]+?)}}", r"`\1`", content)

    # Starting a line with bq. block quotes that line
    content = re.sub(r"bq\. (.*)", r"> \1", content)

    # Wrapping a block of code in {quote}stuff{quote} also block-quotes it
    quote_re = re.compile(r"{quote}(.*?){quote}", re.DOTALL)
    content = re.sub(quote_re, r"~~~ quote\n\1\n~~~", content)

    # {noformat}stuff{noformat} blocks are just code blocks with no
    # syntax highlighting
    noformat_re = re.compile(r"{noformat}(.*?){noformat}", re.DOTALL)
    content = re.sub(noformat_re, r"~~~\n\1\n~~~", content)

    # Code blocks are delineated by {code[: lang]} {code}
    code_re = re.compile(r"{code[^\n]*}(.*?){code}", re.DOTALL)
    content = re.sub(code_re, r"~~~\n\1\n~~~", content)

    # Links are of form: [https://www.google.com] or [Link Title|https://www.google.com]
    # In order to support both forms, we don't match a | in bare links
    content = re.sub(r"\[([^\|~]+?)\]", r"[\1](\1)", content)

    # Full links which have a | are converted into a better Markdown link
    full_link_re = re.compile(r"\[(?:(?P<title>[^|~]+)\|)(?P<url>[^\]]*)\]")
    content = re.sub(full_link_re, r"[\g<title>](\g<url>)", content)

    # We replace mentioned account [~accountid:60e5a86a471e61006a4c51fd]
    # with their corresponding usernames fetched by Jira API.
    url = get_jira_api_url(payload, "rest/api/2/user")
    if url != "":
        content = replace_account_ids_with_usernames(content, realm, url, auth)

    # Here's how Jira escapes special characters in their payload:
    # ,.?\\!\n\"'\n\\[]\\{}()\n@#$%^&*\n~`|/\\\\
    # for some reason, as of writing this, ! has two '\' before it.
    content = content.replace("\\!", "!")

    return content


def get_jira_api_data(jira_api_url: str, get_param: str, auth: Auth | None, **kwargs: Any) -> Any:
    if get_param == "displayName" and auth is None:
        return f"unknown Jira user ({kwargs['accountId'][: MAX_LENGTH - 3] + '...'})"
    if auth:
        response = requests.get(jira_api_url, auth=(auth.email, auth.jira_api_token), params=kwargs)
        if response.status_code != requests.codes.ok:
            if get_param == "displayName":
                return f"unknown Jira user ({kwargs['accountId'][: MAX_LENGTH - 3] + '...'})"
            raise JsonableError(_("Error accessing Jira API."))
        result = response.json()
        return result[get_param]


def replace_account_ids_with_usernames(
    comment: str, realm: Realm, url: str, auth: Auth | None
) -> str:
    pattern = re.compile(r"\[~accountid:([\w\-:]+)\]")
    matches = list(pattern.finditer(comment))
    for match in matches:
        account_id = match.group(1)
        username = get_jira_api_data(url, "displayName", auth, accountId=account_id)
        # We also try to find the Zulip user corresponding to the mention Jira
        # user. We don't know the email, just the Jira username, so we naively
        # guess at their Zulip account using this
        user_profile = guess_zulip_user_from_jira(username, realm)
        if user_profile:
            username = user_profile.full_name
        comment = comment.replace(match.group(0), f"**{username}**")
    return comment


def get_jira_api_url(payload: WildValue, jira_api_path: str) -> str:
    url = get_in(payload, ["comment", "author", "self"]).tame(check_string)
    split_url = urlsplit(url)
    return urlunsplit(split_url._replace(path=jira_api_path, query="", fragment=""))


def get_in(payload: WildValue, keys: list[str], default: str = "") -> WildValue:
    try:
        for key in keys:
            payload = payload[key]
    except (AttributeError, KeyError, TypeError, ValidationError):
        return WildValue("default", default)
    return payload


def get_issue_string(
    payload: WildValue, issue_id: str | None = None, with_title: bool = False
) -> str:
    # Guess the URL as it is not specified in the payload
    # We assume that there is a /browse/BUG-### page
    # from the REST URL of the issue itself
    if issue_id is None:
        issue_id = get_issue_id(payload)

    if with_title:
        text = f"{issue_id}: {get_issue_title(payload)}"
    else:
        text = issue_id

    base_url = re.match(
        r"(.*)\/rest\/api/.*", get_in(payload, ["issue", "self"]).tame(check_string)
    )
    if base_url and len(base_url.groups()):
        return f"[{text}]({base_url.group(1)}/browse/{issue_id})"
    else:
        return text


def get_assignee_mention(assignee_email: str, realm: Realm) -> str:
    if assignee_email != "":
        try:
            assignee_name = get_user_by_delivery_email(assignee_email, realm).full_name
        except UserProfile.DoesNotExist:
            assignee_name = assignee_email
        return f"**{assignee_name}**"
    return ""


def get_issue_author(payload: WildValue) -> str:
    return get_in(payload, ["user", "displayName"]).tame(check_string)


def get_issue_id(payload: WildValue) -> str:
    if "issue" not in payload:
        # Some ancient version of Jira or one of its extensions posts
        # comment_created events without an "issue" element.  For
        # these, the best we can do is extract the Jira-internal
        # issue number and use that in the topic.
        #
        # Users who want better formatting can upgrade Jira.
        return payload["comment"]["self"].tame(check_string).split("/")[-3]

    return get_in(payload, ["issue", "key"]).tame(check_string)


def get_issue_title(payload: WildValue) -> str:
    if "issue" not in payload:
        # Some ancient version of Jira or one of its extensions posts
        # comment_created events without an "issue" element.  For
        # these, the best we can do is extract the Jira-internal
        # issue number and use that in the topic.
        #
        # Users who want better formatting can upgrade Jira.
        return "Upgrade Jira to get the issue title here."

    return get_in(payload, ["issue", "fields", "summary"]).tame(check_string)


def get_issue_topic(payload: WildValue) -> str:
    return f"{get_issue_id(payload)}: {get_issue_title(payload)}"


def get_sub_event_for_update_issue(payload: WildValue) -> str:
    sub_event = payload.get("issue_event_type_name", "").tame(check_string)
    if sub_event == "":
        if payload.get("comment"):
            return "issue_commented"
        elif payload.get("transition"):
            return "issue_transited"
    return sub_event


def get_event_type(payload: WildValue) -> str | None:
    event = payload.get("webhookEvent").tame(check_none_or(check_string))
    if event is None and payload.get("transition"):
        event = "jira:issue_updated"
    return event


def add_change_info(
    content: str, field: str | None, from_field: str | None, to_field: str | None
) -> str:
    content += f"* Changed {field}"
    if from_field:
        content += f" from **{from_field}**"
    if to_field:
        content += f" to {to_field}\n"
    return content


def handle_updated_issue_event(
    payload: WildValue, user_profile: UserProfile, auth: Auth | None
) -> str:
    # Reassigned, commented, reopened, and resolved events are all bundled
    # into this one 'updated' event type, so we try to extract the meaningful
    # event that happened
    issue_id = get_in(payload, ["issue", "key"]).tame(check_string)
    issue = get_issue_string(payload, issue_id, True)

    assignee_email = get_in(payload, ["issue", "fields", "assignee", "emailAddress"], "").tame(
        check_string
    )
    assignee_mention = get_assignee_mention(assignee_email, user_profile.realm)

    if assignee_mention != "":
        assignee_blurb = f" (assigned to {assignee_mention})"
    else:
        assignee_blurb = ""

    sub_event = get_sub_event_for_update_issue(payload)
    if "comment" in sub_event:
        if sub_event == "issue_commented":
            verb = "commented on"
        elif sub_event == "issue_comment_edited":
            verb = "edited a comment on"
        else:
            verb = "deleted a comment from"

        if payload.get("webhookEvent") == "comment_created":
            author = payload["comment"]["author"]["displayName"].tame(check_string)
        else:
            author = get_issue_author(payload)

        content = f"{author} {verb} {issue}{assignee_blurb}"
        comment = get_in(payload, ["comment", "body"]).tame(check_string)
        if comment:
            comment = convert_jira_markup(payload, user_profile.realm, auth)
            content = f"{content}:\n\n``` quote\n{comment}\n```"
        else:
            content = f"{content}."
    else:
        content = f"{get_issue_author(payload)} updated {issue}{assignee_blurb}:\n\n"
        changelog = payload.get("changelog")

        if changelog:
            # Use the changelog to display the changes, whitelist types we accept
            items = changelog.get("items")
            for item in items:
                field = item.get("field").tame(check_none_or(check_string))

                if field == "assignee" and assignee_mention != "":
                    target_field_string = assignee_mention
                else:
                    # Convert a user's target to a @-mention if possible
                    target_field_string = "**{}**".format(
                        item.get("toString").tame(check_none_or(check_string))
                    )

                from_field_string = item.get("fromString").tame(check_none_or(check_string))
                if target_field_string or from_field_string:
                    content = add_change_info(
                        content, field, from_field_string, target_field_string
                    )

        elif sub_event == "issue_transited":
            from_field_string = get_in(payload, ["transition", "from_status"]).tame(check_string)
            target_field_string = "**{}**".format(
                get_in(payload, ["transition", "to_status"]).tame(check_string)
            )
            if target_field_string or from_field_string:
                content = add_change_info(content, "status", from_field_string, target_field_string)

    return content


def handle_created_issue_event(
    payload: WildValue, user_profile: UserProfile, auth: Auth | None
) -> str:
    template = """
{author} created {issue_string}:

* **Priority**: {priority}
* **Assignee**: {assignee}
""".strip()

    return template.format(
        author=get_issue_author(payload),
        issue_string=get_issue_string(payload, with_title=True),
        priority=get_in(payload, ["issue", "fields", "priority", "name"]).tame(check_string),
        assignee=get_in(payload, ["issue", "fields", "assignee", "displayName"], "no one").tame(
            check_string
        ),
    )


def handle_deleted_issue_event(
    payload: WildValue, user_profile: UserProfile, auth: Auth | None
) -> str:
    template = "{author} deleted {issue_string}{punctuation}"
    title = get_issue_title(payload)
    punctuation = "." if title[-1] not in string.punctuation else ""
    return template.format(
        author=get_issue_author(payload),
        issue_string=get_issue_string(payload, with_title=True),
        punctuation=punctuation,
    )


def handle_comment_created_event(
    payload: WildValue, user_profile: UserProfile, auth: Auth | None
) -> str:
    return "{author} commented on {issue_string}\
\n``` quote\n{comment}\n```\n".format(
        author=payload["comment"]["author"]["displayName"].tame(check_string),
        issue_string=get_issue_string(payload, with_title=True),
        comment=convert_jira_markup(payload, user_profile.realm, auth),
    )


def handle_comment_updated_event(
    payload: WildValue, user_profile: UserProfile, auth: Auth | None
) -> str:
    return "{author} updated their comment on {issue_string}\
\n``` quote\n{comment}\n```\n".format(
        author=payload["comment"]["author"]["displayName"].tame(check_string),
        issue_string=get_issue_string(payload, with_title=True),
        comment=convert_jira_markup(payload, user_profile.realm, auth),
    )


def handle_comment_deleted_event(
    payload: WildValue, user_profile: UserProfile, auth: Auth | None
) -> str:
    return "{author} deleted their comment on {issue_string}\
\n``` quote\n~~{comment}~~\n```\n".format(
        author=payload["comment"]["author"]["displayName"].tame(check_string),
        issue_string=get_issue_string(payload, with_title=True),
        comment=convert_jira_markup(payload, user_profile.realm, auth),
    )


JIRA_CONTENT_FUNCTION_MAPPER: dict[
    str, Callable[[WildValue, UserProfile, Auth | None], str] | None
] = {
    "jira:issue_created": handle_created_issue_event,
    "jira:issue_deleted": handle_deleted_issue_event,
    "jira:issue_updated": handle_updated_issue_event,
    "comment_created": handle_comment_created_event,
    "comment_updated": handle_comment_updated_event,
    "comment_deleted": handle_comment_deleted_event,
}

ALL_EVENT_TYPES = list(JIRA_CONTENT_FUNCTION_MAPPER.keys())


@webhook_view("Jira", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_jira_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    jira_api_token: str | None = None,
    email: str | None = None,
) -> HttpResponse:
    event = get_event_type(payload)
    if event in IGNORED_EVENTS:
        return json_success(request)

    if event is None:
        raise AnomalousWebhookPayloadError

    if event is not None:
        content_func = JIRA_CONTENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    auth = None

    if email and jira_api_token is not None:
        # Jira encodes URLs before sending requests to our webhook,
        # which results into double encoding. To address this, we
        # decode the parameters to remove the extra layer of encoding.
        auth = Auth(unquote(email), unquote(jira_api_token))

    topic_name = get_issue_topic(payload)
    content: str = content_func(payload, user_profile, auth)

    check_send_webhook_message(
        request, user_profile, topic_name, content, event, unquote_url_parameters=True
    )
    return json_success(request)
