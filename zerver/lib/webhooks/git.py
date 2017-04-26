from typing import Optional, Any, Dict, List, Text, Tuple
from collections import defaultdict
SUBJECT_WITH_BRANCH_TEMPLATE = u'{repo} / {branch}'
SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE = u'{repo} / {type} #{id} {title}'

EMPTY_SHA = '0000000000000000000000000000000000000000'

COMMITS_LIMIT = 20
COMMIT_ROW_TEMPLATE = u'* {commit_msg} ([{commit_short_sha}]({commit_url}))\n'
COMMITS_MORE_THAN_LIMIT_TEMPLATE = u"[and {commits_number} more commit(s)]"
COMMIT_OR_COMMITS = u"commit{}"

PUSH_PUSHED_TEXT_WITH_URL = u"[pushed]({compare_url}) {number_of_commits} {commit_or_commits}"
PUSH_PUSHED_TEXT_WITHOUT_URL = u"pushed {number_of_commits} {commit_or_commits}"
PUSH_COMMITS_MESSAGE_TEMPLATE_WITH_COMMITTERS = u"""{user_name} {pushed_text} to branch {branch_name}. {committers_details}.

{commits_data}
"""
PUSH_COMMITS_MESSAGE_TEMPLATE_WITHOUT_COMMITTERS = u"""{user_name} {pushed_text} to branch {branch_name}.

{commits_data}
"""
PUSH_COMMITS_MESSAGE_EXTENSION = u"Commits by {}"
PUSH_COMMITTERS_LIMIT_INFO = 3

FORCE_PUSH_COMMITS_MESSAGE_TEMPLATE = u"{user_name} [force pushed]({url}) to branch {branch_name}. Head is now {head}"
CREATE_BRANCH_MESSAGE_TEMPLATE = u"{user_name} created [{branch_name}]({url}) branch"
REMOVE_BRANCH_MESSAGE_TEMPLATE = u"{user_name} deleted branch {branch_name}"

PULL_REQUEST_OR_ISSUE_MESSAGE_TEMPLATE = u"{user_name} {action} [{type}{id}]({url})"
PULL_REQUEST_OR_ISSUE_ASSIGNEE_INFO_TEMPLATE = u"(assigned to {assignee})"
PULL_REQUEST_BRANCH_INFO_TEMPLATE = u"\nfrom `{target}` to `{base}`"

SETUP_MESSAGE_TEMPLATE = u"{integration} webhook has been successfully configured"
SETUP_MESSAGE_USER_PART = u" by {user_name}"

CONTENT_MESSAGE_TEMPLATE = u"\n~~~ quote\n{message}\n~~~"

COMMITS_COMMENT_MESSAGE_TEMPLATE = u"{user_name} {action} on [{sha}]({url})"

PUSH_TAGS_MESSAGE_TEMPLATE = u"""{user_name} {action} tag {tag}"""
TAG_WITH_URL_TEMPLATE = u"[{tag_name}]({tag_url})"
TAG_WITHOUT_URL_TEMPLATE = u"{tag_name}"


def get_push_commits_event_message(user_name, compare_url, branch_name, commits_data, is_truncated=False):
    # type: (Text, Optional[Text], Text, List[Dict[str, Any]], Optional[bool]) -> Text
    pushed_message_template = PUSH_PUSHED_TEXT_WITH_URL if compare_url else PUSH_PUSHED_TEXT_WITHOUT_URL

    pushed_text_message = pushed_message_template.format(
        compare_url=compare_url,
        number_of_commits=len(commits_data),
        commit_or_commits=COMMIT_OR_COMMITS.format(u's' if len(commits_data) > 1 else u''))

    committers_items = get_all_committers(commits_data)  # type: List[Tuple[str, int]]
    if len(committers_items) == 1 and user_name == committers_items[0][0]:
        return PUSH_COMMITS_MESSAGE_TEMPLATE_WITHOUT_COMMITTERS.format(
            user_name=user_name,
            pushed_text=pushed_text_message,
            branch_name=branch_name,
            commits_data=get_commits_content(commits_data, is_truncated),
        ).rstrip()
    else:
        committers_details = "{} ({})".format(*committers_items[0])

        for name, number_of_commits in committers_items[1:-1]:
            committers_details = "{}, {} ({})".format(committers_details, name, number_of_commits)

        if len(committers_items) > 1:
            committers_details = "{} and {} ({})".format(committers_details, *committers_items[-1])

        return PUSH_COMMITS_MESSAGE_TEMPLATE_WITH_COMMITTERS.format(
            user_name=user_name,
            pushed_text=pushed_text_message,
            branch_name=branch_name,
            committers_details=PUSH_COMMITS_MESSAGE_EXTENSION.format(committers_details),
            commits_data=get_commits_content(commits_data, is_truncated),
        ).rstrip()

def get_force_push_commits_event_message(user_name, url, branch_name, head):
    # type: (Text, Text, Text, Text) -> Text
    return FORCE_PUSH_COMMITS_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        url=url,
        branch_name=branch_name,
        head=head
    )

def get_create_branch_event_message(user_name, url, branch_name):
    # type: (Text, Text, Text) -> Text
    return CREATE_BRANCH_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        url=url,
        branch_name=branch_name,
    )

def get_remove_branch_event_message(user_name, branch_name):
    # type: (Text, Text) -> Text
    return REMOVE_BRANCH_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        branch_name=branch_name,
    )

def get_pull_request_event_message(
        user_name, action, url, number=None,
        target_branch=None, base_branch=None,
        message=None, assignee=None, type='PR'
):
    # type: (Text, Text, Text, Optional[int], Optional[Text], Optional[Text], Optional[Text], Optional[Text], Optional[Text]) -> Text
    main_message = PULL_REQUEST_OR_ISSUE_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        action=action,
        type=type,
        url=url,
        id=" #{}".format(number) if number is not None else ''
    )
    if assignee:
        main_message += PULL_REQUEST_OR_ISSUE_ASSIGNEE_INFO_TEMPLATE.format(assignee=assignee)

    if target_branch and base_branch:
        main_message += PULL_REQUEST_BRANCH_INFO_TEMPLATE.format(
            target=target_branch,
            base=base_branch
        )
    if message:
        main_message += '\n' + CONTENT_MESSAGE_TEMPLATE.format(message=message)
    return main_message.rstrip()

def get_setup_webhook_message(integration, user_name=None):
    # type: (Text, Optional[Text]) -> Text
    content = SETUP_MESSAGE_TEMPLATE.format(integration=integration)
    if user_name:
        content += SETUP_MESSAGE_USER_PART.format(user_name=user_name)
    return content

def get_issue_event_message(user_name, action, url, number=None, message=None, assignee=None):
    # type: (Text, Text, Text, Optional[int], Optional[Text], Optional[Text]) -> Text
    return get_pull_request_event_message(
        user_name,
        action,
        url,
        number,
        message=message,
        assignee=assignee,
        type='Issue'
    )

def get_push_tag_event_message(user_name, tag_name, tag_url=None, action='pushed'):
    # type: (Text, Text, Optional[Text], Optional[Text]) -> Text
    if tag_url:
        tag_part = TAG_WITH_URL_TEMPLATE.format(tag_name=tag_name, tag_url=tag_url)
    else:
        tag_part = TAG_WITHOUT_URL_TEMPLATE.format(tag_name=tag_name)
    return PUSH_TAGS_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        action=action,
        tag=tag_part
    )

def get_commits_comment_action_message(user_name, action, commit_url, sha, message=None):
    # type: (Text, Text, Text, Text, Optional[Text]) -> Text
    content = COMMITS_COMMENT_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        action=action,
        sha=get_short_sha(sha),
        url=commit_url
    )
    if message is not None:
        content += CONTENT_MESSAGE_TEMPLATE.format(
            message=message
        )
    return content

def get_commits_content(commits_data, is_truncated=False):
    # type: (List[Dict[str, Any]], Optional[bool]) -> Text
    commits_content = u''
    for commit in commits_data[:COMMITS_LIMIT]:
        commits_content += COMMIT_ROW_TEMPLATE.format(
            commit_short_sha=get_short_sha(commit.get('sha')),
            commit_url=commit.get('url'),
            commit_msg=commit.get('message').partition('\n')[0]
        )

    if len(commits_data) > COMMITS_LIMIT:
        commits_content += COMMITS_MORE_THAN_LIMIT_TEMPLATE.format(
            commits_number=len(commits_data) - COMMITS_LIMIT
        )
    elif is_truncated:
        commits_content += COMMITS_MORE_THAN_LIMIT_TEMPLATE.format(
            commits_number=''
        ).replace('  ', ' ')
    return commits_content.rstrip()

def get_short_sha(sha):
    # type: (Text) -> Text
    return sha[:7]

def get_all_committers(commits_data):
    # type: (List[Dict[str, Any]]) -> List[Tuple[str, int]]
    committers = defaultdict(int)  # type: Dict[str, int]

    for commit in commits_data:
        committers[commit['name']] += 1

    # Sort by commit count, breaking ties alphabetically.
    committers_items = sorted(list(committers.items()),
                              key=lambda item: (-item[1], item[0]))  # type: List[Tuple[str, int]]
    committers_values = [c_i[1] for c_i in committers_items]  # type: List[int]

    if len(committers) > PUSH_COMMITTERS_LIMIT_INFO:
        others_number_of_commits = sum(committers_values[PUSH_COMMITTERS_LIMIT_INFO:])
        committers_items = committers_items[:PUSH_COMMITTERS_LIMIT_INFO]
        committers_items.append(('others', others_number_of_commits))

    return committers_items
