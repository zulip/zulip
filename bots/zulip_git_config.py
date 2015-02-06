# Zulip, Inc's internal git plugin configuration.
# The plugin and example config are under api/integrations/

# Leaving all the instructions out of this file to avoid having to
# sync them as we update the comments.

ZULIP_USER = "commit-bot@zulip.com"
ZULIP_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# commit_notice_destination() lets you customize where commit notices
# are sent to.
#
# It takes the following arguments:
# * repo   = the name of the git repository
# * branch = the name of the branch that was pushed to
# * commit = the commit id
#
# Returns a dictionary encoding the stream and subject to send the
# notification to (or None to send no notification, e.g. for ).
#
# The default code below will send every commit pushed to "master" to
# * stream "commits"
# * topic "master"
# And similarly for branch "test-post-receive" (for use when testing).
def commit_notice_destination(repo, branch, commit):
    if branch in ["master", "prod", "test-post-receive"]:
        return dict(stream  = 'test' if 'test-' in branch else 'commits',
                    subject = u"%s" % (branch,))

    # Return None for cases where you don't want a notice sent
    return None

# Modify this function to change how commits are displayed; the most
# common customization is to include a link to the commit in your
# graphical repository viewer, e.g.
#
# return '!avatar(%s) [%s](https://example.com/commits/%s)\n' % (author, subject, commit_id)
def format_commit_message(author, subject, commit_id):
    return '!avatar(%s) [%s](https://git.zulip.net/eng/zulip/commit/%s)\n' % (author, subject, commit_id)

ZULIP_API_PATH = "/home/zulip/zulip/api"
ZULIP_SITE = "https://zulip.com"
