# Webhooks for external integrations.

from __future__ import absolute_import

from django.conf import settings
from zerver.models import UserProfile, get_client, get_user_profile_by_email
from zerver.lib.actions import check_send_message
from zerver.lib.notifications import  convert_html_to_markdown
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_dict
from zerver.decorator import authenticated_api_view, REQ, \
    has_request_variables, authenticated_rest_api_view, \
    api_key_only_webhook_view, to_non_negative_int, flexible_boolean
from zerver.views.messages import send_message_backend
from django.db.models import Q

from defusedxml.ElementTree import fromstring as xml_fromstring

import pprint
import base64
import logging
import re
import ujson
from functools import wraps

def github_generic_subject(noun, topic_focus, blob):
    # issue and pull_request objects have the same fields we're interested in
    return "%s: %s %d: %s" % (topic_focus, noun, blob['number'], blob['title'])

def github_generic_content(noun, payload, blob):
    action = payload['action']
    if action == 'synchronize':
        action = 'synchronized'

    # issue and pull_request objects have the same fields we're interested in
    content = ("%s %s [%s %s](%s)"
               % (payload['sender']['login'],
                  action,
                  noun,
                  blob['number'],
                  blob['html_url']))
    if payload['action'] in ('opened', 'reopened'):
        content += "\n\n~~~ quote\n%s\n~~~" % (blob['body'],)
    return content


def api_github_v1(user_profile, event, payload, branches, stream, **kwargs):
    """
    processes github payload with version 1 field specification
    `payload` comes in unmodified from github
    `stream` is set to 'commits' if otherwise unset
    """
    commit_stream = stream
    issue_stream = 'issues'
    return api_github_v2(user_profile, event, payload, branches, stream, commit_stream, issue_stream, **kwargs)


def api_github_v2(user_profile, event, payload, branches, default_stream, commit_stream, issue_stream, topic_focus = None):
    """
    processes github payload with version 2 field specification
    `payload` comes in unmodified from github
    `default_stream` is set to what `stream` is in v1 above
    `commit_stream` and `issue_stream` fall back to `default_stream` if they are empty
    This and allowing alternative endpoints is what distinguishes v1 from v2 of the github configuration
    """
    if not commit_stream:
        commit_stream = default_stream
    if not issue_stream:
        issue_stream = default_stream

    target_stream = commit_stream
    repository = payload['repository']

    if not topic_focus:
        topic_focus = repository['name']

    # Event Handlers
    if event == 'pull_request':
        pull_req = payload['pull_request']
        subject = github_generic_subject('pull request', topic_focus, pull_req)
        content = github_generic_content('pull request', payload, pull_req)
    elif event == 'issues':
        # in v1, we assume that this stream exists since it is
        # deprecated and the few realms that use it already have the
        # stream
        target_stream = issue_stream
        issue = payload['issue']
        subject = github_generic_subject('issue', topic_focus, issue)
        content = github_generic_content('issue', payload, issue)
    elif event == 'issue_comment':
        # Comments on both issues and pull requests come in as issue_comment events
        issue = payload['issue']
        if 'pull_request' not in issue or issue['pull_request']['diff_url'] is None:
            # It's an issues comment
            target_stream = issue_stream
            noun = 'issue'
        else:
            # It's a pull request comment
            noun = 'pull request'

        subject = github_generic_subject(noun, topic_focus, issue)
        comment = payload['comment']
        content = ("%s [commented](%s) on [%s %d](%s)\n\n~~~ quote\n%s\n~~~"
                   % (comment['user']['login'],
                      comment['html_url'],
                      noun,
                      issue['number'],
                      issue['html_url'],
                      comment['body']))
    elif event == 'push':
        subject, content = build_message_from_gitlog(user_profile, topic_focus,
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['compare'],
                                                     payload['pusher']['name'],
                                                     forced=payload['forced'],
                                                     created=payload['created'])
    elif event == 'commit_comment':
        comment = payload['comment']
        subject = "%s: commit %s" % (topic_focus, comment['commit_id'])

        content = ("%s [commented](%s)"
                   % (comment['user']['login'],
                      comment['html_url']))

        if comment['line'] is not None:
            content += " on `%s`, line %d" % (comment['path'], comment['line'])

        content += "\n\n~~~ quote\n%s\n~~~" % (comment['body'],)

    return (target_stream, subject, content)

@authenticated_api_view
@has_request_variables
def api_github_landing(request, user_profile, event=REQ,
                       payload=REQ(validator=check_dict([])),
                       branches=REQ(default=''),
                       stream=REQ(default=''),
                       version=REQ(converter=to_non_negative_int, default=1),
                       commit_stream=REQ(default=''),
                       issue_stream=REQ(default=''),
                       exclude_pull_requests=REQ(converter=flexible_boolean, default=False),
                       exclude_issues=REQ(converter=flexible_boolean, default=False),
                       exclude_commits=REQ(converter=flexible_boolean, default=False),
                       emphasize_branch_in_topic=REQ(converter=flexible_boolean, default=False),
                       ):

    repository = payload['repository']

    # Special hook for capturing event data. If we see our special test repo, log the payload from github.
    try:
        if repository['name'] == 'zulip-test' and repository['id'] == 6893087 and settings.PRODUCTION:
            with open('/var/log/zulip/github-payloads', 'a') as f:
                f.write(ujson.dumps({'event': event,
                                     'payload': payload,
                                     'branches': branches,
                                     'stream': stream,
                                     'version': version,
                                     'commit_stream': commit_stream,
                                     'issue_stream': issue_stream,
                                     'exclude_pull_requests': exclude_pull_requests,
                                     'exclude_issues': exclude_issues,
                                     'exclude_commits': exclude_commits,
                                     'emphasize_branch_in_topic': emphasize_branch_in_topic,
                                     }))
                f.write("\n")
    except Exception:
        logging.exception("Error while capturing Github event")

    if not stream:
        stream = 'commits'

    short_ref = re.sub(r'^refs/heads/', '', payload.get('ref', ""))
    kwargs = dict()

    if emphasize_branch_in_topic and short_ref:
        kwargs['topic_focus'] = short_ref

    allowed_events = set()
    if not exclude_pull_requests:
        allowed_events.add('pull_request')

    if not exclude_issues:
        allowed_events.add("issues")
        allowed_events.add("issue_comment")

    if not exclude_commits:
        allowed_events.add("push")
        allowed_events.add("commit_comment")

    if event not in allowed_events:
        return json_success()

    # We filter issue_comment events for issue creation events
    if event == 'issue_comment' and payload['action'] != 'created':
        return json_success()

    if event == 'push':
        # If we are given a whitelist of branches, then we silently ignore
        # any push notification on a branch that is not in our whitelist.
        if branches and short_ref not in re.split('[\s,;|]+', branches):
            return json_success()

    # Map payload to the handler with the right version
    if version == 2:
        target_stream, subject, content = api_github_v2(user_profile, event, payload, branches, stream, commit_stream, issue_stream, **kwargs)
    else:
        target_stream, subject, content = api_github_v1(user_profile, event, payload, branches, stream, **kwargs)

    request.client = get_client("ZulipGitHubWebhook")
    return send_message_backend(request, user_profile,
                                message_type_name="stream",
                                message_to=[target_stream],
                                forged=False, subject_name=subject,
                                message_content=content)

def build_commit_list_content(commits, branch, compare_url, pusher):
    if compare_url is not None:
        push_text = "[pushed](%s)" % (compare_url,)
    else:
        push_text = "pushed"
    content = ("%s %s to branch %s\n\n"
               % (pusher,
                  push_text,
                  branch))
    num_commits = len(commits)
    max_commits = 10
    truncated_commits = commits[:max_commits]
    for commit in truncated_commits:
        short_id = commit['id'][:7]
        (short_commit_msg, _, _) = commit['message'].partition("\n")
        content += "* [%s](%s): %s\n" % (short_id, commit['url'],
                                         short_commit_msg)
    if (num_commits > max_commits):
        content += ("\n[and %d more commits]"
                    % (num_commits - max_commits,))

    return content

def build_message_from_gitlog(user_profile, name, ref, commits, before, after, url, pusher, forced=None, created=None):
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = name

    if re.match(r'^0+$', after):
        content = "%s deleted branch %s" % (pusher,
                                            short_ref)
    # 'created' and 'forced' are github flags; the second check is for beanstalk
    elif (forced and not created) or (forced is None and len(commits) == 0):
        content = ("%s [force pushed](%s) to branch %s.  Head is now %s"
                   % (pusher,
                      url,
                      short_ref,
                      after[:7]))
    else:
        content = build_commit_list_content(commits, short_ref, url, pusher)

    return (subject, content)

def guess_zulip_user_from_jira(jira_username, realm):
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
                replacement = "@**%s**" % (user_profile.full_name,)
            else:
                replacement = "**%s**" % (username,)

            content = content.replace("[~%s]" % (username,), replacement)

    return content

@api_key_only_webhook_view
def api_jira_webhook(request, user_profile):
    try:
        payload = ujson.loads(request.body)
    except ValueError:
        return json_error("Malformed JSON input")

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'jira'

    def get_in(payload, keys, default=''):
        try:
            for key in keys:
                payload = payload[key]
        except (AttributeError, KeyError, TypeError):
            return default
        return payload

    event = payload.get('webhookEvent')
    author = get_in(payload, ['user', 'displayName'])
    issueId = get_in(payload, ['issue', 'key'])
    # Guess the URL as it is not specified in the payload
    # We assume that there is a /browse/BUG-### page
    # from the REST url of the issue itself
    baseUrl = re.match("(.*)\/rest\/api/.*", get_in(payload, ['issue', 'self']))
    if baseUrl and len(baseUrl.groups()):
        issue = "[%s](%s/browse/%s)" % (issueId, baseUrl.group(1), issueId)
    else:
        issue = issueId
    title = get_in(payload, ['issue', 'fields', 'summary'])
    priority = get_in(payload, ['issue', 'fields', 'priority', 'name'])
    assignee = get_in(payload, ['issue', 'fields', 'assignee', 'displayName'], 'no one')
    assignee_email = get_in(payload, ['issue', 'fields', 'assignee', 'emailAddress'], '')
    assignee_mention = ''
    if assignee_email != '':
        try:
            assignee_profile = get_user_profile_by_email(assignee_email)
            assignee_mention = "@**%s**" % (assignee_profile.full_name,)
        except UserProfile.DoesNotExist:
            assignee_mention = "**%s**" % (assignee_email,)

    subject = "%s: %s" % (issueId, title)

    if event == 'jira:issue_created':
        content = "%s **created** %s priority %s, assigned to **%s**:\n\n> %s" % \
                  (author, issue, priority, assignee, title)
    elif event == 'jira:issue_deleted':
        content = "%s **deleted** %s!" % \
                  (author, issue)
    elif event == 'jira:issue_updated':
        # Reassigned, commented, reopened, and resolved events are all bundled
        # into this one 'updated' event type, so we try to extract the meaningful
        # event that happened
        if assignee_mention != '':
            assignee_blurb = " (assigned to %s)" % (assignee_mention,)
        else:
            assignee_blurb = ''
        content = "%s **updated** %s%s:\n\n" % (author, issue, assignee_blurb)
        changelog = get_in(payload, ['changelog',])
        comment = get_in(payload, ['comment', 'body'])

        if changelog != '':
            # Use the changelog to display the changes, whitelist types we accept
            items = changelog.get('items')
            for item in items:
                field = item.get('field')

                # Convert a user's target to a @-mention if possible
                targetFieldString = "**%s**" % (item.get('toString'),)
                if field == 'assignee' and assignee_mention != '':
                    targetFieldString = assignee_mention

                fromFieldString = item.get('fromString')
                if targetFieldString or fromFieldString:
                    content += "* Changed %s from **%s** to %s\n" % (field, fromFieldString, targetFieldString)

        if comment != '':
            comment = convert_jira_markup(comment, user_profile.realm)
            content += "\n%s\n" % (comment,)
    elif event in ['jira:worklog_updated']:
        # We ignore these event types
        return json_success()
    elif 'transition' in payload:
        from_status = get_in(payload, ['transition', 'from_status'])
        to_status = get_in(payload, ['transition', 'to_status'])
        content = "%s **transitioned** %s from %s to %s" % (author, issue, from_status, to_status)
    else:
        # Unknown event type
        if not settings.TEST_SUITE:
            if event is None:
                logging.warning("Got JIRA event with None event type: %s" % (payload,))
            else:
                logging.warning("Got JIRA event type we don't understand: %s" % (event,))
        return json_error("Unknown JIRA event type")

    check_send_message(user_profile, get_client("ZulipJIRAWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

def api_pivotal_webhook_v3(request, user_profile, stream):
    payload = xml_fromstring(request.body)

    def get_text(attrs):
        start = payload
        try:
            for attr in attrs:
                start = start.find(attr)
            return start.text
        except AttributeError:
            return ""

    event_type = payload.find('event_type').text
    description = payload.find('description').text
    project_id = payload.find('project_id').text
    story_id = get_text(['stories', 'story', 'id'])
    # Ugh, the URL in the XML data is not a clickable url that works for the user
    # so we try to build one that the user can actually click on
    url = "https://www.pivotaltracker.com/s/projects/%s/stories/%s" % (project_id, story_id)

    # Pivotal doesn't tell us the name of the story, but it's usually in the
    # description in quotes as the first quoted string
    name_re = re.compile(r'[^"]+"([^"]+)".*')
    match = name_re.match(description)
    if match and len(match.groups()):
        name = match.group(1)
    else:
        name = "Story changed" # Failed for an unknown reason, show something
    more_info = " [(view)](%s)" % (url,)

    if event_type == 'story_update':
        subject = name
        content = description + more_info
    elif event_type == 'note_create':
        subject = "Comment added"
        content = description +  more_info
    elif event_type == 'story_create':
        issue_desc = get_text(['stories', 'story', 'description'])
        issue_type = get_text(['stories', 'story', 'story_type'])
        issue_status = get_text(['stories', 'story', 'current_state'])
        estimate = get_text(['stories', 'story', 'estimate'])
        if estimate != '':
            estimate = " worth %s story points" % (estimate,)
        subject = name
        content = "%s (%s %s%s):\n\n~~~ quote\n%s\n~~~\n\n%s" % (description,
                                                   issue_status,
                                                   issue_type,
                                                   estimate,
                                                   issue_desc,
                                                   more_info)
    return subject, content

def api_pivotal_webhook_v5(request, user_profile, stream):
    payload = ujson.loads(request.body)

    event_type = payload["kind"]

    project_name = payload["project"]["name"]
    project_id = payload["project"]["id"]

    primary_resources = payload["primary_resources"][0]
    story_url = primary_resources["url"]
    story_type = primary_resources["story_type"]
    story_id = primary_resources["id"]
    story_name = primary_resources["name"]

    performed_by = payload.get("performed_by", {}).get("name", "")

    story_info = "[%s](https://www.pivotaltracker.com/s/projects/%s): [%s](%s)" % (project_name, project_id, story_name, story_url)

    changes = payload.get("changes", [])

    content = ""
    subject = "#%s: %s" % (story_id, story_name)

    def extract_comment(change):
        if change.get("kind") == "comment":
            return change.get("new_values", {}).get("text", None)
        return None

    if event_type == "story_update_activity":
        # Find the changed valued and build a message
        content += "%s updated %s:\n" % (performed_by, story_info)
        for change in changes:
            old_values = change.get("original_values", {})
            new_values = change["new_values"]

            if "current_state" in old_values and "current_state" in new_values:
                content += "* state changed from **%s** to **%s**\n" % (old_values["current_state"], new_values["current_state"])
            if "estimate" in old_values and "estimate" in new_values:
                old_estimate = old_values.get("estimate", None)
                if old_estimate is None:
                    estimate = "is now"
                else:
                    estimate = "changed from %s to" % (old_estimate,)
                new_estimate = new_values["estimate"] if new_values["estimate"] is not None else "0"
                content += "* estimate %s **%s points**\n" % (estimate, new_estimate)
            if "story_type" in old_values and "story_type" in new_values:
                content += "* type changed from **%s** to **%s**\n" % (old_values["story_type"], new_values["story_type"])

            comment = extract_comment(change)
            if comment is not None:
                content += "* Comment added:\n~~~quote\n%s\n~~~\n" % (comment,)

    elif event_type == "comment_create_activity":
        for change in changes:
            comment = extract_comment(change)
            if comment is not None:
                content += "%s added a comment to %s:\n~~~quote\n%s\n~~~" % (performed_by, story_info, comment)
    elif event_type == "story_create_activity":
        content += "%s created %s: %s\n" % (performed_by, story_type, story_info)
        for change in changes:
            new_values = change.get("new_values", {})
            if "current_state" in new_values:
                content += "* State is **%s**\n" % (new_values["current_state"],)
            if "description" in new_values:
                content += "* Description is\n\n> %s" % (new_values["description"],)
    elif event_type == "story_move_activity":
        content = "%s moved %s" % (performed_by, story_info)
        for change in changes:
            old_values = change.get("original_values", {})
            new_values = change["new_values"]
            if "current_state" in old_values and "current_state" in new_values:
                content += " from **%s** to **%s**" % (old_values["current_state"], new_values["current_state"])
    elif event_type in ["task_create_activity", "comment_delete_activity",
                        "task_delete_activity", "task_update_activity",
                        "story_move_from_project_activity", "story_delete_activity",
                        "story_move_into_project_activity"]:
        # Known but unsupported Pivotal event types
        pass
    else:
        logging.warning("Unknown Pivotal event type: %s" % (event_type,))

    return subject, content

@api_key_only_webhook_view
def api_pivotal_webhook(request, user_profile):
    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing stream parameter.")

    subject = content = None
    try:
        subject, content = api_pivotal_webhook_v3(request, user_profile, stream)
    except AttributeError:
        return json_error("Failed to extract data from Pivotal XML response")
    except:
        # Attempt to parse v5 JSON payload
        try:
            subject, content = api_pivotal_webhook_v5(request, user_profile, stream)
        except AttributeError:
            return json_error("Failed to extract data from Pivotal V5 JSON response")

    if subject is None or content is None:
        return json_error("Unable to handle Pivotal payload")

    check_send_message(user_profile, get_client("ZulipPivotalWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

# Beanstalk's web hook UI rejects url with a @ in the username section of a url
# So we ask the user to replace them with %40
# We manually fix the username here before passing it along to @authenticated_rest_api_view
def beanstalk_decoder(view_func):
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        try:
            auth_type, encoded_value = request.META['HTTP_AUTHORIZATION'].split()
            if auth_type.lower() == "basic":
                email, api_key = base64.b64decode(encoded_value).split(":")
                email = email.replace('%40', '@')
                request.META['HTTP_AUTHORIZATION'] = "Basic %s" % (base64.b64encode("%s:%s" % (email, api_key)))
        except:
            pass

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func

@beanstalk_decoder
@authenticated_rest_api_view
@has_request_variables
def api_beanstalk_webhook(request, user_profile,
                          payload=REQ(validator=check_dict([]))):
    # Beanstalk supports both SVN and git repositories
    # We distinguish between the two by checking for a
    # 'uri' key that is only present for git repos
    git_repo = 'uri' in payload
    if git_repo:
        # To get a linkable url,
        subject, content = build_message_from_gitlog(user_profile, payload['repository']['name'],
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['repository']['url'],
                                                     payload['pusher_name'])
    else:
        author = payload.get('author_full_name')
        url = payload.get('changeset_url')
        revision = payload.get('revision')
        (short_commit_msg, _, _) = payload.get('message').partition("\n")

        subject = "svn r%s" % (revision,)
        content = "%s pushed [revision %s](%s):\n\n> %s" % (author, revision, url, short_commit_msg)

    check_send_message(user_profile, get_client("ZulipBeanstalkWebhook"), "stream",
                       ["commits"], subject, content)
    return json_success()

# Desk.com's integrations all make the user supply a template, where it fills
# in stuff like {{customer.name}} and posts the result as a "data" parameter.
# There's no raw JSON for us to work from. Thus, it makes sense to just write
# a template Zulip message within Desk.com and have the webhook extract that
# from the "data" param and post it, which this does.
@authenticated_rest_api_view
@has_request_variables
def api_deskdotcom_webhook(request, user_profile, data=REQ(),
                           topic=REQ(default="Desk.com notification"),
                           stream=REQ(default="desk.com")):
    check_send_message(user_profile, get_client("ZulipDeskWebhook"), "stream",
                       [stream], topic, data)
    return json_success()

@api_key_only_webhook_view
@has_request_variables
def api_newrelic_webhook(request, user_profile, alert=REQ(validator=check_dict([]), default=None),
                             deployment=REQ(validator=check_dict([]), default=None)):
    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing stream parameter.")

    if alert:
        # Use the message as the subject because it stays the same for
        # "opened", "acknowledged", and "closed" messages that should be
        # grouped.
        subject = alert['message']
        content = "%(long_description)s\n[View alert](%(alert_url)s)" % (alert)
    elif deployment:
        subject = "%s deploy" % (deployment['application_name'])
        content = """`%(revision)s` deployed by **%(deployed_by)s**
%(description)s

%(changelog)s""" % (deployment)
    else:
        return json_error("Unknown webhook request")

    check_send_message(user_profile, get_client("ZulipNewRelicWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

@authenticated_rest_api_view
@has_request_variables
def api_bitbucket_webhook(request, user_profile, payload=REQ(validator=check_dict([])),
                          stream=REQ(default='commits')):
    repository = payload['repository']
    commits = [{'id': commit['raw_node'], 'message': commit['message'],
                'url': '%s%scommits/%s' % (payload['canon_url'],
                                           repository['absolute_url'],
                                           commit['raw_node'])}
               for commit in payload['commits']]

    subject = repository['name']
    if len(commits) == 0:
        # Bitbucket doesn't give us enough information to really give
        # a useful message :/
        content = ("%s [force pushed](%s)"
                   % (payload['user'],
                      payload['canon_url'] + repository['absolute_url']))
    else:
        branch = payload['commits'][-1]['branch']
        content = build_commit_list_content(commits, branch, None, payload['user'])
        subject += '/%s' % (branch,)

    check_send_message(user_profile, get_client("ZulipBitBucketWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

@authenticated_rest_api_view
@has_request_variables
def api_stash_webhook(request, user_profile, stream=REQ(default='')):
    try:
        payload = ujson.loads(request.body)
    except ValueError:
        return json_error("Malformed JSON input")

    # We don't get who did the push, or we'd try to report that.
    try:
        repo_name = payload["repository"]["name"]
        project_name = payload["repository"]["project"]["name"]
        branch_name = payload["refChanges"][0]["refId"].split("/")[-1]
        commit_entries = payload["changesets"]["values"]
        commits = [(entry["toCommit"]["displayId"],
                    entry["toCommit"]["message"].split("\n")[0]) for \
                       entry in commit_entries]
        head_ref = commit_entries[-1]["toCommit"]["displayId"]
    except KeyError as e:
        return json_error("Missing key %s in JSON" % (e.message,))

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'commits'

    subject = "%s/%s: %s" % (project_name, repo_name, branch_name)

    content = "`%s` was pushed to **%s** in **%s/%s** with:\n\n" % (
        head_ref, branch_name, project_name, repo_name)
    content += "\n".join("* `%s`: %s" % (
            commit[0], commit[1]) for commit in commits)

    check_send_message(user_profile, get_client("ZulipStashWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

class TicketDict(dict):
    """
    A helper class to turn a dictionary with ticket information into
    an object where each of the keys is an attribute for easy access.
    """
    def __getattr__(self, field):
        if "_" in field:
            return self.get(field)
        else:
            return self.get("ticket_" + field)

def property_name(property, index):
    # The Freshdesk API is currently pretty broken: statuses are customizable
    # but the API will only tell you the number associated with the status, not
    # the name. While we engage the Freshdesk developers about exposing this
    # information through the API, since only FlightCar uses this integration,
    # hardcode their statuses.
    statuses = ["", "", "Open", "Pending", "Resolved", "Closed",
                "Waiting on Customer", "Job Application", "Monthly"]
    priorities = ["", "Low", "Medium", "High", "Urgent"]

    if property == "status":
        return statuses[index] if index < len(statuses) else str(index)
    elif property == "priority":
        return priorities[index] if index < len(priorities) else str(index)
    else:
        raise ValueError("Unknown property")

def parse_freshdesk_event(event_string):
    # These are always of the form "{ticket_action:created}" or
    # "{status:{from:4,to:6}}". Note the lack of string quoting: this isn't
    # valid JSON so we have to parse it ourselves.
    data = event_string.replace("{", "").replace("}", "").replace(",", ":").split(":")

    if len(data) == 2:
        # This is a simple ticket action event, like
        # {ticket_action:created}.
        return data
    else:
        # This is a property change event, like {status:{from:4,to:6}}. Pull out
        # the property, from, and to states.
        property, _, from_state, _, to_state = data
        return (property, property_name(property, int(from_state)),
                property_name(property, int(to_state)))

def format_freshdesk_note_message(ticket, event_info):
    # There are public (visible to customers) and private note types.
    note_type = event_info[1]
    content = "%s <%s> added a %s note to [ticket #%s](%s)." % (
        ticket.requester_name, ticket.requester_email, note_type,
        ticket.id, ticket.url)

    return content

def format_freshdesk_property_change_message(ticket, event_info):
    # Freshdesk will only tell us the first event to match our webhook
    # configuration, so if we change multiple properties, we only get the before
    # and after data for the first one.
    content = "%s <%s> updated [ticket #%s](%s):\n\n" % (
        ticket.requester_name, ticket.requester_email, ticket.id, ticket.url)
    # Why not `"%s %s %s" % event_info`? Because the linter doesn't like it.
    content += "%s: **%s** => **%s**" % (
        event_info[0].capitalize(), event_info[1], event_info[2])

    return content

def format_freshdesk_ticket_creation_message(ticket):
    # They send us the description as HTML.
    cleaned_description = convert_html_to_markdown(ticket.description)
    content = "%s <%s> created [ticket #%s](%s):\n\n" % (
        ticket.requester_name, ticket.requester_email, ticket.id, ticket.url)
    content += """~~~ quote
%s
~~~\n
""" % (cleaned_description,)
    content += "Type: **%s**\nPriority: **%s**\nStatus: **%s**" % (
        ticket.type, ticket.priority, ticket.status)

    return content

@authenticated_rest_api_view
@has_request_variables
def api_freshdesk_webhook(request, user_profile, stream=REQ(default='')):
    try:
        payload = ujson.loads(request.body)
        ticket_data = payload["freshdesk_webhook"]
    except ValueError:
        return json_error("Malformed JSON input")

    required_keys = [
        "triggered_event", "ticket_id", "ticket_url", "ticket_type",
        "ticket_subject", "ticket_description", "ticket_status",
        "ticket_priority", "requester_name", "requester_email",
        ]

    for key in required_keys:
        if ticket_data.get(key) is None:
            logging.warning("Freshdesk webhook error. Payload was:")
            logging.warning(request.body)
            return json_error("Missing key %s in JSON" % (key,))

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'freshdesk'

    ticket = TicketDict(ticket_data)

    subject = "#%s: %s" % (ticket.id, ticket.subject)

    try:
        event_info = parse_freshdesk_event(ticket.triggered_event)
    except ValueError:
        return json_error("Malformed event %s" % (ticket.triggered_event,))

    if event_info[1] == "created":
        content = format_freshdesk_ticket_creation_message(ticket)
    elif event_info[0] == "note_type":
        content = format_freshdesk_note_message(ticket, event_info)
    elif event_info[0] in ("status", "priority"):
        content = format_freshdesk_property_change_message(ticket, event_info)
    else:
        # Not an event we know handle; do nothing.
        return json_success()

    check_send_message(user_profile, get_client("ZulipFreshdeskWebhook"), "stream",
                       [stream], subject, content)
    return json_success()

def truncate(string, length):
    if len(string) > length:
        string = string[:length-3] + '...'
    return string

@authenticated_rest_api_view
def api_zendesk_webhook(request, user_profile):
    """
    Zendesk uses trigers with message templates. This webhook uses the
    ticket_id and ticket_title to create a subject. And passes with zendesk
    user's configured message to zulip.
    """
    try:
        ticket_title = request.POST['ticket_title']
        ticket_id = request.POST['ticket_id']
        message = request.POST['message']
        stream = request.POST.get('stream', 'zendesk')
    except KeyError as e:
        return json_error('Missing post parameter %s' % (e.message,))

    subject = truncate('#%s: %s' % (ticket_id, ticket_title), 60)
    check_send_message(user_profile, get_client('ZulipZenDeskWebhook'), 'stream',
                       [stream], subject, message)
    return json_success()


PAGER_DUTY_EVENT_NAMES = {
    'incident.trigger': 'triggered',
    'incident.acknowledge': 'acknowledged',
    'incident.unacknowledge': 'unacknowledged',
    'incident.resolve': 'resolved',
    'incident.assign': 'assigned',
    'incident.escalate': 'escalated',
    'incident.delegate': 'delineated',
}

def build_pagerduty_formatdict(message):
    # Normalize the message dict, after this all keys will exist. I would
    # rather some strange looking messages than dropping pages.

    format_dict = {}
    format_dict['action'] = PAGER_DUTY_EVENT_NAMES[message['type']]

    format_dict['incident_id'] = message['data']['incident']['id']
    format_dict['incident_num'] = message['data']['incident']['incident_number']
    format_dict['incident_url'] = message['data']['incident']['html_url']

    format_dict['service_name'] = message['data']['incident']['service']['name']
    format_dict['service_url'] = message['data']['incident']['service']['html_url']

    # This key can be missing on null
    if message['data']['incident'].get('assigned_to_user', None):
        format_dict['assigned_to_email'] = message['data']['incident']['assigned_to_user']['email']
        format_dict['assigned_to_username'] = message['data']['incident']['assigned_to_user']['email'].split('@')[0]
        format_dict['assigned_to_url'] = message['data']['incident']['assigned_to_user']['html_url']
    else:
        format_dict['assigned_to_email'] = 'nobody'
        format_dict['assigned_to_username'] = 'nobody'
        format_dict['assigned_to_url'] = ''

    # This key can be missing on null
    if message['data']['incident'].get('resolved_by_user', None):
        format_dict['resolved_by_email'] = message['data']['incident']['resolved_by_user']['email']
        format_dict['resolved_by_username'] = message['data']['incident']['resolved_by_user']['email'].split('@')[0]
        format_dict['resolved_by_url'] = message['data']['incident']['resolved_by_user']['html_url']
    else:
        format_dict['resolved_by_email'] = 'nobody'
        format_dict['resolved_by_username'] = 'nobody'
        format_dict['resolved_by_url'] = ''

    trigger_message = []
    trigger_subject = message['data']['incident']['trigger_summary_data'].get('subject', '')
    if trigger_subject:
        trigger_message.append(trigger_subject)
    trigger_description = message['data']['incident']['trigger_summary_data'].get('description', '')
    if trigger_description:
        trigger_message.append(trigger_description)
    format_dict['trigger_message'] = u'\n'.join(trigger_message)
    return format_dict


def send_raw_pagerduty_json(user_profile, stream, message, topic):
    subject = topic or 'pagerduty'
    body = (
        u'Unknown pagerduty message\n'
        u'``` py\n'
        u'%s\n'
        u'```') % (pprint.pformat(message),)
    check_send_message(user_profile, get_client('ZulipPagerDutyWebhook'), 'stream',
                       [stream], subject, body)


def send_formated_pagerduty(user_profile, stream, message_type, format_dict, topic):
    if message_type in ('incident.trigger', 'incident.unacknowledge'):
        template = (u':imp: Incident '
        u'[{incident_num}]({incident_url}) {action} by '
        u'[{service_name}]({service_url}) and assigned to '
        u'[{assigned_to_username}@]({assigned_to_url})\n\n>{trigger_message}')

    elif message_type == 'incident.resolve' and format_dict['resolved_by_url']:
        template = (u':grinning: Incident '
        u'[{incident_num}]({incident_url}) resolved by '
        u'[{resolved_by_username}@]({resolved_by_url})\n\n>{trigger_message}')
    elif message_type == 'incident.resolve' and not format_dict['resolved_by_url']:
        template = (u':grinning: Incident '
        u'[{incident_num}]({incident_url}) resolved\n\n>{trigger_message}')
    else:
        template = (u':no_good: Incident [{incident_num}]({incident_url}) '
        u'{action} by [{assigned_to_username}@]({assigned_to_url})\n\n>{trigger_message}')

    subject = topic or u'incident {incident_num}'.format(**format_dict)
    body = template.format(**format_dict)

    check_send_message(user_profile, get_client('ZulipPagerDutyWebhook'), 'stream',
                       [stream], subject, body)


@api_key_only_webhook_view
@has_request_variables
def api_pagerduty_webhook(request, user_profile, stream=REQ(default='pagerduty'), topic=REQ(default=None)):
    payload = ujson.loads(request.body)

    for message in payload['messages']:
        message_type = message['type']

        if message_type not in PAGER_DUTY_EVENT_NAMES:
            send_raw_pagerduty_json(user_profile, stream, message, topic)

        try:
            format_dict = build_pagerduty_formatdict(message)
        except:
            send_raw_pagerduty_json(user_profile, stream, message, topic)
        else:
            send_formated_pagerduty(user_profile, stream, message_type, format_dict, topic)

    return json_success()
