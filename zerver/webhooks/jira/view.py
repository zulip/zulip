# Webhooks for external integrations.
import re
import string
from typing import Any, Callable, Dict, List, Optional

from django.db.models import Q
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import Realm, UserProfile, get_user_by_delivery_email

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

def guess_zulip_user_from_jira(jira_username: str, realm: Realm) -> Optional[UserProfile]:
    try:
        # Try to find a matching user in Zulip
        # We search a user's full name, short name,
        # and beginning of email address
        user = UserProfile.objects.filter(
            Q(full_name__iexact=jira_username) |
            Q(email__istartswith=jira_username),
            is_active=True,
            realm=realm).order_by("id")[0]
        return user
    except IndexError:
        return None

def convert_jira_markup(content: str, realm: Realm) -> str:
    # Attempt to do some simplistic conversion of JIRA
    # formatting to Markdown, for consumption in Zulip

    # Jira uses *word* for bold, we use **word**
    content = re.sub(r'\*([^\*]+)\*', r'**\1**', content)

    # Jira uses {{word}} for monospacing, we use `word`
    content = re.sub(r'{{([^\*]+?)}}', r'`\1`', content)

    # Starting a line with bq. block quotes that line
    content = re.sub(r'bq\. (.*)', r'> \1', content)

    # Wrapping a block of code in {quote}stuff{quote} also block-quotes it
    quote_re = re.compile(r'{quote}(.*?){quote}', re.DOTALL)
    content = re.sub(quote_re, r'~~~ quote\n\1\n~~~', content)

    # {noformat}stuff{noformat} blocks are just code blocks with no
    # syntax highlighting
    noformat_re = re.compile(r'{noformat}(.*?){noformat}', re.DOTALL)
    content = re.sub(noformat_re, r'~~~\n\1\n~~~', content)

    # Code blocks are delineated by {code[: lang]} {code}
    code_re = re.compile(r'{code[^\n]*}(.*?){code}', re.DOTALL)
    content = re.sub(code_re, r'~~~\n\1\n~~~', content)

    # Links are of form: [https://www.google.com] or [Link Title|https://www.google.com]
    # In order to support both forms, we don't match a | in bare links
    content = re.sub(r'\[([^\|~]+?)\]', r'[\1](\1)', content)

    # Full links which have a | are converted into a better Markdown link
    full_link_re = re.compile(r'\[(?:(?P<title>[^|~]+)\|)(?P<url>[^\]]*)\]')
    content = re.sub(full_link_re, r'[\g<title>](\g<url>)', content)

    # Try to convert a JIRA user mention of format [~username] into a
    # Zulip user mention. We don't know the email, just the JIRA username,
    # so we naively guess at their Zulip account using this
    if realm:
        mention_re = re.compile('\\[~(.*?)\\]')
        for username in mention_re.findall(content):
            # Try to look up username
            user_profile = guess_zulip_user_from_jira(username, realm)
            if user_profile:
                replacement = f"**{user_profile.full_name}**"
            else:
                replacement = f"**{username}**"

            content = content.replace(f"[~{username}]", replacement)

    return content

def get_in(payload: Dict[str, Any], keys: List[str], default: str='') -> Any:
    try:
        for key in keys:
            payload = payload[key]
    except (AttributeError, KeyError, TypeError):
        return default
    return payload

def get_issue_string(payload: Dict[str, Any], issue_id: Optional[str]=None, with_title: bool=False) -> str:
    # Guess the URL as it is not specified in the payload
    # We assume that there is a /browse/BUG-### page
    # from the REST URL of the issue itself
    if issue_id is None:
        issue_id = get_issue_id(payload)

    if with_title:
        text = f"{issue_id}: {get_issue_title(payload)}"
    else:
        text = issue_id

    base_url = re.match(r"(.*)\/rest\/api/.*", get_in(payload, ['issue', 'self']))
    if base_url and len(base_url.groups()):
        return f"[{text}]({base_url.group(1)}/browse/{issue_id})"
    else:
        return text

def get_assignee_mention(assignee_email: str, realm: Realm) -> str:
    if assignee_email != '':
        try:
            assignee_name = get_user_by_delivery_email(assignee_email, realm).full_name
        except UserProfile.DoesNotExist:
            assignee_name = assignee_email
        return f"**{assignee_name}**"
    return ''

def get_issue_author(payload: Dict[str, Any]) -> str:
    return get_in(payload, ['user', 'displayName'])

def get_issue_id(payload: Dict[str, Any]) -> str:
    if 'issue' not in payload:
        # Some ancient version of Jira or one of its extensions posts
        # comment_created events without an "issue" element.  For
        # these, the best we can do is extract the Jira-intenral
        # issue number and use that in the topic.
        #
        # Users who want better formatting can upgrade Jira.
        return payload['comment']['self'].split('/')[-3]

    return get_in(payload, ['issue', 'key'])

def get_issue_title(payload: Dict[str, Any]) -> str:
    if 'issue' not in payload:
        # Some ancient version of Jira or one of its extensions posts
        # comment_created events without an "issue" element.  For
        # these, the best we can do is extract the Jira-intenral
        # issue number and use that in the topic.
        #
        # Users who want better formatting can upgrade Jira.
        return 'Upgrade Jira to get the issue title here.'

    return get_in(payload, ['issue', 'fields', 'summary'])

def get_issue_subject(payload: Dict[str, Any]) -> str:
    return f"{get_issue_id(payload)}: {get_issue_title(payload)}"

def get_sub_event_for_update_issue(payload: Dict[str, Any]) -> str:
    sub_event = payload.get('issue_event_type_name', '')
    if sub_event == '':
        if payload.get('comment'):
            return 'issue_commented'
        elif payload.get('transition'):
            return 'issue_transited'
    return sub_event

def get_event_type(payload: Dict[str, Any]) -> Optional[str]:
    event = payload.get('webhookEvent')
    if event is None and payload.get('transition'):
        event = 'jira:issue_updated'
    return event

def add_change_info(content: str, field: str, from_field: str, to_field: str) -> str:
    content += f"* Changed {field}"
    if from_field:
        content += f" from **{from_field}**"
    if to_field:
        content += f" to {to_field}\n"
    return content

def handle_updated_issue_event(payload: Dict[str, Any], user_profile: UserProfile) -> str:
    # Reassigned, commented, reopened, and resolved events are all bundled
    # into this one 'updated' event type, so we try to extract the meaningful
    # event that happened
    issue_id = get_in(payload, ['issue', 'key'])
    issue = get_issue_string(payload, issue_id, True)

    assignee_email = get_in(payload, ['issue', 'fields', 'assignee', 'emailAddress'], '')
    assignee_mention = get_assignee_mention(assignee_email, user_profile.realm)

    if assignee_mention != '':
        assignee_blurb = f" (assigned to {assignee_mention})"
    else:
        assignee_blurb = ''

    sub_event = get_sub_event_for_update_issue(payload)
    if 'comment' in sub_event:
        if sub_event == 'issue_commented':
            verb = 'commented on'
        elif sub_event == 'issue_comment_edited':
            verb = 'edited a comment on'
        else:
            verb = 'deleted a comment from'

        if payload.get('webhookEvent') == 'comment_created':
            author = payload['comment']['author']['displayName']
        else:
            author = get_issue_author(payload)

        content = f"{author} {verb} {issue}{assignee_blurb}"
        comment = get_in(payload, ['comment', 'body'])
        if comment:
            comment = convert_jira_markup(comment, user_profile.realm)
            content = f"{content}:\n\n``` quote\n{comment}\n```"
        else:
            content = f"{content}."
    else:
        content = f"{get_issue_author(payload)} updated {issue}{assignee_blurb}:\n\n"
        changelog = get_in(payload, ['changelog'])

        if changelog != '':
            # Use the changelog to display the changes, whitelist types we accept
            items = changelog.get('items')
            for item in items:
                field = item.get('field')

                if field == 'assignee' and assignee_mention != '':
                    target_field_string = assignee_mention
                else:
                    # Convert a user's target to a @-mention if possible
                    target_field_string = "**{}**".format(item.get('toString'))

                from_field_string = item.get('fromString')
                if target_field_string or from_field_string:
                    content = add_change_info(content, field, from_field_string, target_field_string)

        elif sub_event == 'issue_transited':
            from_field_string = get_in(payload, ['transition', 'from_status'])
            target_field_string = '**{}**'.format(get_in(payload, ['transition', 'to_status']))
            if target_field_string or from_field_string:
                content = add_change_info(content, 'status', from_field_string, target_field_string)

    return content

def handle_created_issue_event(payload: Dict[str, Any], user_profile: UserProfile) -> str:
    template = """
{author} created {issue_string}:

* **Priority**: {priority}
* **Assignee**: {assignee}
""".strip()

    return template.format(
        author=get_issue_author(payload),
        issue_string=get_issue_string(payload, with_title=True),
        priority=get_in(payload, ['issue', 'fields', 'priority', 'name']),
        assignee=get_in(payload, ['issue', 'fields', 'assignee', 'displayName'], 'no one'),
    )

def handle_deleted_issue_event(payload: Dict[str, Any], user_profile: UserProfile) -> str:
    template = "{author} deleted {issue_string}{punctuation}"
    title = get_issue_title(payload)
    punctuation = '.' if title[-1] not in string.punctuation else ''
    return template.format(
        author=get_issue_author(payload),
        issue_string=get_issue_string(payload, with_title=True),
        punctuation=punctuation,
    )

def normalize_comment(comment: str) -> str:
    # Here's how Jira escapes special characters in their payload:
    # ,.?\\!\n\"'\n\\[]\\{}()\n@#$%^&*\n~`|/\\\\
    # for some reason, as of writing this, ! has two '\' before it.
    normalized_comment = comment.replace("\\!", "!")
    return normalized_comment

def handle_comment_created_event(payload: Dict[str, Any], user_profile: UserProfile) -> str:
    title = get_issue_title(payload)
    return "{author} commented on issue: *\"{title}\"\
*\n``` quote\n{comment}\n```\n".format(
        author = payload["comment"]["author"]["displayName"],
        title = title,
        comment = normalize_comment(payload["comment"]["body"]),
    )

def handle_comment_updated_event(payload: Dict[str, Any], user_profile: UserProfile) -> str:
    title = get_issue_title(payload)
    return "{author} updated their comment on issue: *\"{title}\"\
*\n``` quote\n{comment}\n```\n".format(
        author = payload["comment"]["author"]["displayName"],
        title = title,
        comment = normalize_comment(payload["comment"]["body"]),
    )

def handle_comment_deleted_event(payload: Dict[str, Any], user_profile: UserProfile) -> str:
    title = get_issue_title(payload)
    return "{author} deleted their comment on issue: *\"{title}\"\
*\n``` quote\n~~{comment}~~\n```\n".format(
        author = payload["comment"]["author"]["displayName"],
        title = title,
        comment = normalize_comment(payload["comment"]["body"]),
    )

JIRA_CONTENT_FUNCTION_MAPPER = {
    "jira:issue_created": handle_created_issue_event,
    "jira:issue_deleted": handle_deleted_issue_event,
    "jira:issue_updated": handle_updated_issue_event,
    "comment_created": handle_comment_created_event,
    "comment_updated": handle_comment_updated_event,
    "comment_deleted": handle_comment_deleted_event,
}

def get_event_handler(event: Optional[str]) -> Optional[Callable[..., str]]:
    if event is None:
        return None

    return JIRA_CONTENT_FUNCTION_MAPPER.get(event)

@webhook_view("JIRA")
@has_request_variables
def api_jira_webhook(request: HttpRequest, user_profile: UserProfile,
                     payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    event = get_event_type(payload)
    if event in IGNORED_EVENTS:
        return json_success()

    content_func = get_event_handler(event)

    if content_func is None:
        raise UnsupportedWebhookEventType(event)

    subject = get_issue_subject(payload)
    content: str = content_func(payload, user_profile)

    check_send_webhook_message(request, user_profile,
                               subject, content,
                               unquote_url_parameters=True)
    return json_success()
