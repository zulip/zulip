from django.conf.urls import url
import zerver.views
import zerver.views.streams
import zerver.views.invite
import zerver.views.user_settings
import zerver.views.auth
import zerver.views.tutorial
import zerver.views.report
import zerver.views.upload
import zerver.views.messages
import zerver.views.muting

# Future endpoints should add to urls.py, which includes these legacy urls

legacy_urls = [
    # These are json format views used by the web client.  They require a logged in browser.

    # We should remove this endpoint and all code related to it.
    # It returns a 404 if the stream doesn't exist, which is confusing
    # for devs, and I don't think we need to go to the server
    # any more to find out about subscriptions, since they are already
    # pushed to us via the event system.
    url(r'^json/subscriptions/exists$', zerver.views.streams.json_stream_exists),

    url(r'^json/fetch_api_key$', zerver.views.auth.json_fetch_api_key),
    # This old-style tutorial is due to be eliminated soon.
    url(r'^json/tutorial_send_message$', zerver.views.tutorial.json_tutorial_send_message),
    url(r'^json/tutorial_status$', zerver.views.tutorial.json_tutorial_status),
    # A version of these reporting views may make sense to support in
    # the API for getting mobile analytics, but we may want something
    # totally different.
    url(r'^json/report_error$', zerver.views.report.json_report_error),
    url(r'^json/report_send_time$', zerver.views.report.json_report_send_time),
    url(r'^json/report_narrow_time$', zerver.views.report.json_report_narrow_time),
    url(r'^json/report_unnarrow_time$', zerver.views.report.json_report_unnarrow_time),
]
