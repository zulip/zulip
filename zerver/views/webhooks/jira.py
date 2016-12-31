# Webhooks for external integrations.
from __future__ import absolute_import
from typing import Any, Optional, Text, Tuple

from django.utils.translation import ugettext as _
from django.db.models import Q
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from zerver.models import Client, UserProfile, get_user_profile_by_email, Realm
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import api_key_only_webhook_view, has_request_variables, REQ

import logging
import re
import ujson

def guess_zulip_user_from_jira(jira_username, realm):
    # type: (str, Realm) -> Optional[UserProfile]
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

def convert_jira_markup(content, realm):
    # type: (str, Realm) -> str
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
        mention_re = re.compile(r'\[~(.*?)\]')
        for username in mention_re.findall(content):
            # Try to look up username
            user_profile = guess_zulip_user_from_jira(username, realm)
            if user_profile:
                replacement = "**{}**".format(user_profile.full_name)
            else:
                replacement = "**{}**".format(username)

            content = content.replace("[~{}]".format(username,), replacement)

    return content

def get_in(payload, keys, default=''):
    # type: (Dict[str, Any], List[str], str) -> Any
    try:
        for key in keys:
            payload = payload[key]
    except (AttributeError, KeyError, TypeError):
        return default
    return payload

def handle_issue_event(event, payload, user_profile):
    # type: (Text, Dict[str, Any], Any) -> Tuple[Text, Text]
    author = get_in(payload, ['user', 'displayName'])
    issue_id = get_in(payload, ['issue', 'key'])

    # Guess the URL as it is not specified in the payload
    # We assume that there is a /browse/BUG-### page
    # from the REST url of the issue itself
    base_url = re.match("(.*)\/rest\/api/.*", get_in(payload, ['issue', 'self']))
    if base_url and len(base_url.groups()):
        issue = "[{}]({}/browse/{})".format(issue_id, base_url.group(1), issue_id)
    else:
        issue = issue_id

    title = get_in(payload, ['issue', 'fields', 'summary'])
    priority = get_in(payload, ['issue', 'fields', 'priority', 'name'])
    assignee = get_in(payload, ['issue', 'fields', 'assignee', 'displayName'], 'no one')
    assignee_email = get_in(payload, ['issue', 'fields', 'assignee', 'emailAddress'], '')
    assignee_mention = ''

    if assignee_email != '':
        try:
            assignee_profile = get_user_profile_by_email(assignee_email)
            assignee_mention = "**{}**".format(assignee_profile.full_name)
        except UserProfile.DoesNotExist:
            assignee_mention = "**{}**".format(assignee_email)

    subject = "{}: {}".format(issue_id, title)

    if event == 'jira:issue_created':
        content = "{} **created** {} priority {}, assigned to **{}**:\n\n> {}".format(
            author,
            issue,
            priority,
            assignee,
            title
        )

    elif event == 'jira:issue_deleted':
        content = "{} **deleted** {}!".format(author, issue)

    elif event == 'jira:issue_updated':
        # Reassigned, commented, reopened, and resolved events are all bundled
        # into this one 'updated' event type, so we try to extract the meaningful
        # event that happened
        if assignee_mention != '':
            assignee_blurb = " (assigned to {})".format(assignee_mention)
        else:
            assignee_blurb = ''
        content = "{} **updated** {}{}:\n\n".format(author, issue, assignee_blurb)
        changelog = get_in(payload, ['changelog'])
        comment = get_in(payload, ['comment', 'body'])

        if changelog != '':
            # Use the changelog to display the changes, whitelist types we accept
            items = changelog.get('items')
            for item in items:
                field = item.get('field')

                # Convert a user's target to a @-mention if possible
                target_field_string = "**{}**".format(item.get('toString'))

                if field == 'assignee' and assignee_mention != '':
                    target_field_string = assignee_mention

                from_field_string = item.get('fromString')
                if target_field_string or from_field_string:
                    content += "* Changed {} from **{}** to {}\n".format(field, from_field_string, target_field_string)

        if comment != '':
            comment = convert_jira_markup(comment, user_profile.realm)
            content += "\n{}\n".format(comment)
    else:
        content = None
        subject = None
    return content, subject


@api_key_only_webhook_view("JIRA")
@has_request_variables
def api_jira_webhook(request, user_profile, client,
                     payload=REQ(argument_type='body'),
                     stream=REQ(default='jira')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], Text) -> HttpResponse

    event = payload.get('webhookEvent')
    if event.startswith('jira:issue'):
        content, subject = handle_issue_event(event, payload, user_profile)
    else:
        # Unknown event type
        if not settings.TEST_SUITE:
            if event is None:
                logging.warning("Got JIRA event with None event type: {}".format(payload))
            else:
                logging.warning("Got JIRA event type we don't understand: {}".format(event))
        return json_error(_("Unknown JIRA event type"))

    if content is None or subject is None:
        return json_error(_("Event {} is not supported".format(event)))

    check_send_message(user_profile, client, "stream",
                       [stream], subject, content)
    return json_success()
