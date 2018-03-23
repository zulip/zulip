# Webhooks for external integrations.
import logging
import re
from typing import Any, Dict, List, Optional, Text, Tuple

import ujson
from django.conf import settings
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import Realm, UserProfile, get_user

IGNORED_EVENTS = [
    'comment_created',  # we handle issue_update event instead
    'comment_updated',  # we handle issue_update event instead
    'comment_deleted',  # we handle issue_update event instead
]

def guess_zulip_user_from_jira(jira_username: Text, realm: Realm) -> Optional[UserProfile]:
    try:
        # Try to find a matching user in Zulip
        # We search a user's full name, short name,
        # and beginning of email address
        user = UserProfile.objects.filter(
            Q(full_name__iexact=jira_username) |
            Q(short_name__iexact=jira_username) |
            Q(email__istartswith=jira_username),
            is_active=True,
            realm=realm).order_by("id")[0]
        return user
    except IndexError:
        return None

def convert_jira_markup(content: Text, realm: Realm) -> Text:
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

    # Full links which have a | are converted into a better markdown link
    full_link_re = re.compile(r'\[(?:(?P<title>[^|~]+)\|)(?P<url>.*)\]')
    content = re.sub(full_link_re, r'[\g<title>](\g<url>)', content)

    # Try to convert a JIRA user mention of format [~username] into a
    # Zulip user mention. We don't know the email, just the JIRA username,
    # so we naively guess at their Zulip account using this
    if realm:
        mention_re = re.compile(u'\[~(.*?)\]')
        for username in mention_re.findall(content):
            # Try to look up username
            user_profile = guess_zulip_user_from_jira(username, realm)
            if user_profile:
                replacement = u"**{}**".format(user_profile.full_name)
            else:
                replacement = u"**{}**".format(username)

            content = content.replace("[~{}]".format(username,), replacement)

    return content

def get_in(payload: Dict[str, Any], keys: List[str], default: Text='') -> Any:
    try:
        for key in keys:
            payload = payload[key]
    except (AttributeError, KeyError, TypeError):
        return default
    return payload

def get_issue_string(payload: Dict[str, Any], issue_id: Optional[Text]=None) -> Text:
    # Guess the URL as it is not specified in the payload
    # We assume that there is a /browse/BUG-### page
    # from the REST url of the issue itself
    if issue_id is None:
        issue_id = get_issue_id(payload)

    base_url = re.match("(.*)\/rest\/api/.*", get_in(payload, ['issue', 'self']))
    if base_url and len(base_url.groups()):
        return u"[{}]({}/browse/{})".format(issue_id, base_url.group(1), issue_id)
    else:
        return issue_id

def get_assignee_mention(assignee_email: Text, realm: Realm) -> Text:
    if assignee_email != '':
        try:
            assignee_name = get_user(assignee_email, realm).full_name
        except UserProfile.DoesNotExist:
            assignee_name = assignee_email
        return u"**{}**".format(assignee_name)
    return ''

def get_issue_author(payload: Dict[str, Any]) -> Text:
    return get_in(payload, ['user', 'displayName'])

def get_issue_id(payload: Dict[str, Any]) -> Text:
    return get_in(payload, ['issue', 'key'])

def get_issue_title(payload: Dict[str, Any]) -> Text:
    return get_in(payload, ['issue', 'fields', 'summary'])

def get_issue_subject(payload: Dict[str, Any]) -> Text:
    return u"{}: {}".format(get_issue_id(payload), get_issue_title(payload))

def get_sub_event_for_update_issue(payload: Dict[str, Any]) -> Text:
    sub_event = payload.get('issue_event_type_name', '')
    if sub_event == '':
        if payload.get('comment'):
            return 'issue_commented'
        elif payload.get('transition'):
            return 'issue_transited'
    return sub_event

def get_event_type(payload: Dict[str, Any]) -> Optional[Text]:
    event = payload.get('webhookEvent')
    if event is None and payload.get('transition'):
        event = 'jira:issue_updated'
    return event

def add_change_info(content: Text, field: Text, from_field: Text, to_field: Text) -> Text:
    content += u"* Changed {}".format(field)
    if from_field:
        content += u" from **{}**".format(from_field)
    if to_field:
        content += u" to {}\n".format(to_field)
    return content

def handle_updated_issue_event(payload: Dict[str, Any], user_profile: UserProfile) -> Text:
    # Reassigned, commented, reopened, and resolved events are all bundled
    # into this one 'updated' event type, so we try to extract the meaningful
    # event that happened
    issue_id = get_in(payload, ['issue', 'key'])
    issue = get_issue_string(payload, issue_id)

    assignee_email = get_in(payload, ['issue', 'fields', 'assignee', 'emailAddress'], '')
    assignee_mention = get_assignee_mention(assignee_email, user_profile.realm)

    if assignee_mention != '':
        assignee_blurb = u" (assigned to {})".format(assignee_mention)
    else:
        assignee_blurb = ''

    sub_event = get_sub_event_for_update_issue(payload)
    if 'comment' in sub_event:
        if sub_event == 'issue_commented':
            verb = 'added comment to'
        elif sub_event == 'issue_comment_edited':
            verb = 'edited comment on'
        else:
            verb = 'deleted comment from'
        content = u"{} **{}** {}{}".format(get_issue_author(payload), verb, issue, assignee_blurb)
        comment = get_in(payload, ['comment', 'body'])
        if comment:
            comment = convert_jira_markup(comment, user_profile.realm)
            content = u"{}:\n\n\n{}\n".format(content, comment)
    else:
        content = u"{} **updated** {}{}:\n\n".format(get_issue_author(payload), issue, assignee_blurb)
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
                    target_field_string = u"**{}**".format(item.get('toString'))

                from_field_string = item.get('fromString')
                if target_field_string or from_field_string:
                    content = add_change_info(content, field, from_field_string, target_field_string)

        elif sub_event == 'issue_transited':
            from_field_string = get_in(payload, ['transition', 'from_status'])
            target_field_string = u'**{}**'.format(get_in(payload, ['transition', 'to_status']))
            if target_field_string or from_field_string:
                content = add_change_info(content, 'status', from_field_string, target_field_string)

    return content

def handle_created_issue_event(payload: Dict[str, Any]) -> Text:
    return u"{} **created** {} priority {}, assigned to **{}**:\n\n> {}".format(
        get_issue_author(payload),
        get_issue_string(payload),
        get_in(payload, ['issue', 'fields', 'priority', 'name']),
        get_in(payload, ['issue', 'fields', 'assignee', 'displayName'], 'no one'),
        get_issue_title(payload)
    )

def handle_deleted_issue_event(payload: Dict[str, Any]) -> Text:
    return u"{} **deleted** {}!".format(get_issue_author(payload), get_issue_string(payload))

@api_key_only_webhook_view("JIRA")
@has_request_variables
def api_jira_webhook(request: HttpRequest, user_profile: UserProfile,
                     payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    event = get_event_type(payload)
    if event == 'jira:issue_created':
        subject = get_issue_subject(payload)
        content = handle_created_issue_event(payload)
    elif event == 'jira:issue_deleted':
        subject = get_issue_subject(payload)
        content = handle_deleted_issue_event(payload)
    elif event == 'jira:issue_updated':
        subject = get_issue_subject(payload)
        content = handle_updated_issue_event(payload, user_profile)
    elif event in IGNORED_EVENTS:
        return json_success()
    else:
        if event is None:
            if not settings.TEST_SUITE:
                message = u"Got JIRA event with None event type: {}".format(payload)
                logging.warning(message)
            return json_error(_("Event is not given by JIRA"))
        else:
            if not settings.TEST_SUITE:
                logging.warning("Got JIRA event type we don't support: {}".format(event))
            return json_success()

    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()
