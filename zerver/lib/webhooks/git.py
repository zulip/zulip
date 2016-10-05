from six import text_type
from typing import Optional, Any

SUBJECT_WITH_BRANCH_TEMPLATE = u'{repo} / {branch}'

PUSH_COMMITS_LIMIT = 10
PUSH_PUSHED_TEXT_WITH_URL = u"[pushed]({compare_url})"
PUSH_PUSHED_TEXT_WITHOUT_URL = u"pushed"
PUSH_COMMIT_ROW_TEMPLATE = u'* [{commit_short_sha}]({commit_url}): {commit_msg}\n'
PUSH_COMMITS_MORE_THAN_LIMIT_TEMPLATE = u"[and {commits_number} more commit(s)]"
PUSH_COMMITS_MESSAGE_TEMPLATE = u"""{user_name} {pushed_text} to branch {branch_name}

{commits_list}
{commits_more_than_limit}
"""

def get_push_commits_event_message(user_name, compare_url, branch_name, commits_data):
    # type: (text_type, Optional[text_type], text_type, List[Dict[str, Any]]) -> text_type
    commits_list_message = u''
    for commit in commits_data[:PUSH_COMMITS_LIMIT]:
        commits_list_message += PUSH_COMMIT_ROW_TEMPLATE.format(
            commit_short_sha=commit.get('sha')[:7],
            commit_url=commit.get('url'),
            commit_msg=commit.get('message').partition('\n')[0]
        )

    if len(commits_data) > PUSH_COMMITS_LIMIT:
        commits_more_than_limit_message = PUSH_COMMITS_MORE_THAN_LIMIT_TEMPLATE.format(
            commits_number=len(commits_data) - PUSH_COMMITS_LIMIT)
    else:
        commits_more_than_limit_message = ''

    if compare_url:
        pushed_text_message = PUSH_PUSHED_TEXT_WITH_URL.format(compare_url=compare_url)
    else:
        pushed_text_message = PUSH_PUSHED_TEXT_WITHOUT_URL

    return PUSH_COMMITS_MESSAGE_TEMPLATE.format(
        user_name=user_name,
        pushed_text=pushed_text_message,
        branch_name=branch_name,
        commits_list=commits_list_message.rstrip(),
        commits_more_than_limit=commits_more_than_limit_message
    ).rstrip()
