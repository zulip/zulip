# Zulip, Inc's internal trac plugin configuration.
# The plugin and example config are under api/integrations/

# Leaving all the instructions out of this file to avoid having to
# sync them as we update the comments.

ZULIP_USER = "trac-bot@zulip.com"
ZULIP_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
STREAM_FOR_NOTIFICATIONS = "trac"
TRAC_BASE_TICKET_URL = "https://trac.zulip.net/ticket"

TRAC_NOTIFY_FIELDS = ["description", "summary", "resolution", "comment", "owner"]
ZULIP_API_PATH = "/home/zulip/zulip/api"
ZULIP_SITE = "https://zulip.com"
