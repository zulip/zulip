# Webhooks for external integrations.

from __future__ import absolute_import

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from zerver.models import UserProfile, get_client, MAX_SUBJECT_LENGTH
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import rate_limit_user, authenticated_api_view, REQ, \
    has_request_variables, json_to_dict, authenticated_rest_api_view
from zerver.views import send_message_backend

from defusedxml.ElementTree import fromstring as xml_fromstring

import base64
import logging
import re
import ujson
from functools import wraps

@authenticated_api_view
@has_request_variables
def api_github_landing(request, user_profile, event=REQ,
                       payload=REQ(converter=json_to_dict),
                       branches=REQ(default=''),
                       stream=REQ(default='')):
    # TODO: this should all be moved to an external bot
    repository = payload['repository']

    # Special hook for capturing event data
    try:
        if repository['name'] == 'zulip-test':
            with open('/var/log/humbug/github-payloads', 'a') as f:
                f.write(ujson.dumps({'event': event, 'payload': payload}))
                f.write("\n")
    except Exception:
        logging.exception("Error while capturing Github event")

    if not stream:
        stream = 'commits'

    # CUSTOMER18 has requested not to get pull request notifications
    if event == 'pull_request' and user_profile.realm.domain not in ['customer18.invalid', 'zulip.com']:
        pull_req = payload['pull_request']

        subject = "%s: pull request %d" % (repository['name'],
                                           pull_req['number'])
        content = ("Pull request from %s [%s](%s):\n\n %s\n\n> %s"
                   % (pull_req['user']['login'],
                      payload['action'],
                      pull_req['html_url'],
                      pull_req['title'],
                      pull_req['body']))
    elif event == 'push':
        short_ref = re.sub(r'^refs/heads/', '', payload['ref'])
        # This is a bit hackish, but is basically so that CUSTOMER18 doesn't
        # get spammed when people commit to non-master all over the place.
        # Long-term, this will be replaced by some GitHub configuration
        # option of which branches to notify on.
        if short_ref != 'master' and user_profile.realm.domain in ['customer18.invalid', 'zulip.com']:
            return json_success()

        if branches:
            # If we are given a whitelist of branches, then we silently ignore
            # any push notification on a branch that is not in our whitelist.
            if short_ref not in re.split('[\s,;|]+', branches):
                return json_success()


        subject, content = build_message_from_gitlog(user_profile, repository['name'],
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['compare'],
                                                     payload['pusher']['name'])
    elif event == 'issues':
        if user_profile.realm.domain not in ('zulip.com', 'customer5.invalid'):
            return json_success()

        issue = payload['issue']
        subject = "%s: issue %d %s" % (repository['name'], issue['number'], payload['action'])
        content = ("%s %s [issue %d](%s): %s\n\n> %s"
                   % (issue['user']['login'],
                      payload['action'],
                      issue['number'],
                      issue['html_url'],
                      issue['title'],
                      issue['body']))
        stream = 'issues'
    else:
        # We don't handle other events even though we get notified
        # about them
        return json_success()

    subject = elide_subject(subject)

    request.client = get_client("github_bot")
    return send_message_backend(request, user_profile,
                                message_type_name="stream",
                                message_to=[stream],
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

def build_message_from_gitlog(user_profile, name, ref, commits, before, after, url, pusher):
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = name

    if re.match(r'^0+$', after):
        content = "%s deleted branch %s" % (pusher,
                                            short_ref)
    elif len(commits) == 0:
        content = ("%s [force pushed](%s) to branch %s.  Head is now %s"
                   % (pusher,
                      url,
                      short_ref,
                      after[:7]))
    else:
        content = build_commit_list_content(commits, short_ref, url, pusher)

    return (subject, content)

def elide_subject(subject):
    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[:57].rstrip() + '...'
    return subject

@csrf_exempt
def api_jira_webhook(request):
    try:
        api_key = request.GET['api_key']
    except (AttributeError, KeyError):
        return json_error("Missing api_key parameter.")

    try:
        payload = ujson.loads(request.body)
    except ValueError:
        return json_error("Malformed JSON input")

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'jira'

    try:
        user_profile = UserProfile.objects.get(api_key=api_key)
        request.user = user_profile
    except UserProfile.DoesNotExist:
        return json_error("Failed to find user with API key: %s" % (api_key,))

    rate_limit_user(request, user_profile, domain='all')

    def get_in(payload, keys, default=''):
        try:
            for key in keys:
                payload = payload[key]
        except (AttributeError, KeyError):
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
    assignee = get_in(payload, ['assignee', 'displayName'], 'no one')
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
        content = "%s **updated** %s:\n\n" % (author, issue)
        changelog = get_in(payload, ['changelog',])
        comment = get_in(payload, ['comment', 'body'])

        if changelog != '':
            # Use the changelog to display the changes, whitelist types we accept
            items = changelog.get('items')
            for item in items:
                field = item.get('field')
                if field in ('status', 'assignee'):
                    content += "* Changed %s from **%s** to **%s**\n" % (field, item.get('fromString'), item.get('toString'))

        if comment != '':
            content += "\n> %s" % (comment,)
    elif 'transition' in payload:
        from_status = get_in(payload, ['transition', 'from_status'])
        to_status = get_in(payload, ['transition', 'to_status'])
        content = "%s **transitioned** %s from %s to %s" % (author, issue, from_status, to_status)
    else:
        # Unknown event type
        if not settings.TEST_SUITE:
            logging.warning("Got JIRA event type we don't understand: %s" % (event,))
        return json_error("Unknown JIRA event type")

    subject = elide_subject(subject)

    check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
    return json_success()

@csrf_exempt
def api_pivotal_webhook(request):
    try:
        api_key = request.GET['api_key']
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing api_key or stream parameter.")

    try:
        user_profile = UserProfile.objects.get(api_key=api_key)
        request.user = user_profile
    except UserProfile.DoesNotExist:
        return json_error("Failed to find user with API key: %s" % (api_key,))

    rate_limit_user(request, user_profile, domain='all')

    payload = xml_fromstring(request.body)

    def get_text(attrs):
        start = payload
        try:
            for attr in attrs:
                start = start.find(attr)
            return start.text
        except AttributeError:
            return ""

    try:
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
            content = "%s (%s %s%s):\n\n> %s\n\n%s" % (description,
                                                       issue_status,
                                                       issue_type,
                                                       estimate,
                                                       issue_desc,
                                                       more_info)

    except AttributeError:
        return json_error("Failed to extract data from Pivotal XML response")

    subject = elide_subject(subject)

    check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
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
                          payload=REQ(converter=json_to_dict)):
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

    subject = elide_subject(subject)

    check_send_message(user_profile, get_client("API"), "stream", ["commits"], subject, content)
    return json_success()

# Desk.com's integrations all make the user supply a template, where it fills
# in stuff like {{customer.name}} and posts the result as a "data" parameter.
# There's no raw JSON for us to work from. Thus, it makes sense to just write
# a template Zulip message within Desk.com and have the webhook extract that
# from the "data" param and post it, which this does.
@csrf_exempt
@authenticated_rest_api_view
@has_request_variables
def api_deskdotcom_webhook(request, user_profile, data=REQ(),
                           topic=REQ(default="Desk.com notification"),
                           stream=REQ(default="desk.com")):
    check_send_message(user_profile, get_client("API"), "stream", [stream], topic, data)
    return json_success()

@csrf_exempt
@has_request_variables
def api_newrelic_webhook(request, alert=REQ(converter=json_to_dict, default=None),
                             deployment=REQ(converter=json_to_dict, default=None)):
    try:
        api_key = request.GET['api_key']
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing api_key or stream parameter.")

    try:
        user_profile = UserProfile.objects.get(api_key=api_key)
        request.user = user_profile
    except UserProfile.DoesNotExist:
        return json_error("Failed to find user with API key: %s" % (api_key,))

    rate_limit_user(request, user_profile, domain='all')

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

    subject = elide_subject(subject)
    check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
    return json_success()

@authenticated_rest_api_view
@has_request_variables
def api_bitbucket_webhook(request, user_profile, payload=REQ(converter=json_to_dict),
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
        content = build_commit_list_content(commits, payload['commits'][-1]['branch'],
                                            None, payload['user'])

    subject = elide_subject(subject)
    check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
    return json_success()
