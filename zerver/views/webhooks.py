# Webhooks for external integrations.

from __future__ import absolute_import

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from zerver.models import UserProfile, get_client, MAX_SUBJECT_LENGTH, \
      get_user_profile_by_email
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import authenticated_api_view, REQ, \
    has_request_variables, json_to_dict, authenticated_rest_api_view, \
    api_key_only_webhook_view
from zerver.views import send_message_backend
from django.db.models import Q

from defusedxml.ElementTree import fromstring as xml_fromstring

import base64
import logging
import re
import ujson
from functools import wraps

def github_generic_subject(noun, repository, blob):
    # issue and pull_request objects have the same fields we're interested in
    return "%s: %s %d: %s" % (repository['name'], noun, blob['number'], blob['title'])

def github_generic_content(noun, payload, blob):
    # issue and pull_request objects have the same fields we're interested in
    content = ("%s %s [%s %s](%s)"
               % (blob['user']['login'],
                  payload['action'],
                  noun,
                  blob['number'],
                  blob['html_url']))
    if payload['action'] in ('opened', 'reopened'):
        content += "\n\n~~~ quote\n%s\n~~~" % (blob['body'],)
    return content

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
        if repository['name'] == 'zulip-test' and settings.DEPLOYED:
            with open('/var/log/zulip/github-payloads', 'a') as f:
                f.write(ujson.dumps({'event': event, 'payload': payload}))
                f.write("\n")
    except Exception:
        logging.exception("Error while capturing Github event")

    if not stream:
        stream = 'commits'

    # CUSTOMER18 has requested not to get pull request notifications
    if event == 'pull_request' and user_profile.realm.domain not in ['customer18.invalid']:
        pull_req = payload['pull_request']
        subject = github_generic_subject('pull request', repository, pull_req)
        content = github_generic_content('pull request', payload, pull_req)
    elif event == 'issues':
        if user_profile.realm.domain in ('customer37.invalid', 'customer38.invalid'):
            return json_success()

        if user_profile.realm.domain not in ('zulip.com', 'customer5.invalid'):
            return json_success()

        stream = 'issues'
        issue = payload['issue']
        subject = github_generic_subject('issue', repository, issue)
        content = github_generic_content('issue', payload, issue)
    elif event == 'issue_comment':
        if user_profile.realm.domain in ('customer37.invalid', 'customer38.invalid'):
            return json_success()

        if payload['action'] != 'created':
            return json_success()

        # Comments on both issues and pull requests come in as issue_comment events
        issue = payload['issue']
        if issue['pull_request']['diff_url'] is None:
            # It's an issues comment
            stream = 'issues'
            noun = 'issue'
        else:
            # It's a pull request comment
            noun = 'pull request'

        subject = github_generic_subject(noun, repository, issue)
        comment = payload['comment']
        content = ("%s [commented](%s) on [%s %d](%s)\n\n~~~ quote\n%s\n~~~"
                   % (comment['user']['login'],
                      comment['html_url'],
                      noun,
                      issue['number'],
                      issue['html_url'],
                      comment['body']))
    elif event == 'push':
        if user_profile.realm.domain in ('customer37.invalid', 'customer38.invalid'):
            return json_success()

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
    elif event == 'commit_comment':
        comment = payload['comment']
        subject = "%s: commit %s" % (repository['name'], comment['commit_id'])

        content = ("%s [commented](%s)"
                   % (comment['user']['login'],
                      comment['html_url']))

        if comment['position'] is not None:
            content += " on `%s`, line %d" % (comment['path'], comment['line'])

        content += "\n\n~~~ quote\n%s\n~~~" % (comment['body'],)
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

                if field in ('status', 'assignee'):
                    content += "* Changed %s from **%s** to %s\n" % (field, item.get('fromString'), targetFieldString)

        if comment != '':
            comment = convert_jira_markup(comment, user_profile.realm)
            content += "\n%s\n" % (comment,)
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

@api_key_only_webhook_view
def api_pivotal_webhook(request, user_profile):
    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing stream parameter.")

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
            content = "%s (%s %s%s):\n\n~~~ quote\n%s\n~~~\n\n%s" % (description,
                                                       issue_status,
                                                       issue_type,
                                                       estimate,
                                                       issue_desc,
                                                       more_info)
        else:
            logging.warning("Received Pivotal event we did not understand: %s" % (event_type, ))
            return json_success()

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

@api_key_only_webhook_view
@has_request_variables
def api_newrelic_webhook(request, user_profile, alert=REQ(converter=json_to_dict, default=None),
                             deployment=REQ(converter=json_to_dict, default=None)):
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
        branch = payload['commits'][-1]['branch']
        content = build_commit_list_content(commits, branch, None, payload['user'])
        subject += '/%s' % (branch,)

    subject = elide_subject(subject)
    check_send_message(user_profile, get_client("API"), "stream", [stream], subject, content)
    return json_success()

@csrf_exempt
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
    except KeyError, e:
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

    check_send_message(user_profile, get_client("Stash"), "stream", [stream],
                       subject, content)
    return json_success()
