# Humbug Inc's internal git plugin configuration.
# The plugin and example config are under api/integrations/

# Leaving all the instructions out of this file to avoid having to
# sync them as we update the comments.

HUMBUG_USER = "humbug+commits@humbughq.com"
HUMBUG_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

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
# * subject "deploy => master" (using a pretty unicode right arrow)
# And similarly for branch "test-post-receive" (for use when testing).
def commit_notice_destination(repo, branch, commit):
    if branch in ["master", "post-receive-test"]:
        return dict(stream  = "commits",
                    subject = u"deploy \u21D2 %s" % (branch,))

    # Return None for cases where you don't want a notice sent
    return None

HUMBUG_API_PATH = "/home/humbug/humbug/api"
HUMBUG_SITE = "https://staging.humbughq.com"
