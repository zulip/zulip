# Humbug Inc's internal trac plugin configuration.
# The plugin and example config are under api/integrations/

# Leaving all the instructions out of this file to avoid having to
# sync them as we update the comments.

HUMBUG_USER = "humbug+trac@humbughq.com"
HUMBUG_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
STREAM_FOR_NOTIFICATIONS = "trac"
TRAC_BASE_TICKET_URL = "https://trac.humbughq.com/ticket"

TRAC_NOTIFY_FIELDS = ["description", "summary", "resolution", "comment"]
HUMBUG_API_PATH = "/home/humbug/humbug/api"
HUMBUG_SITE = "https://staging.humbughq.com"
