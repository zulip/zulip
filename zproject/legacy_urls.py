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
    url(r'^json/invite_users$', zerver.views.invite.json_invite_users),
    url(r'^json/refer_friend$', zerver.views.invite.json_refer_friend),
    url(r'^json/settings/change$', zerver.views.user_settings.json_change_settings),

    # We should remove this endpoint and all code related to it.
    # It returns a 404 if the stream doesn't exist, which is confusing
    # for devs, and I don't think we need to go to the server
    # any more to find out about subscriptions, since they are already
    # pushed to us via the event system.
    url(r'^json/subscriptions/exists$', zerver.views.streams.json_stream_exists),

    url(r'^json/subscriptions/property$', zerver.views.streams.json_subscription_property),
    url(r'^json/fetch_api_key$', zerver.views.auth.json_fetch_api_key),
    url(r'^json/tutorial_send_message$', zerver.views.tutorial.json_tutorial_send_message),
    url(r'^json/tutorial_status$', zerver.views.tutorial.json_tutorial_status),
    url(r'^json/report_error$', zerver.views.report.json_report_error),
    url(r'^json/report_send_time$', zerver.views.report.json_report_send_time),
    url(r'^json/report_narrow_time$', zerver.views.report.json_report_narrow_time),
    url(r'^json/report_unnarrow_time$', zerver.views.report.json_report_unnarrow_time),
    url(r'^json/upload_file$', zerver.views.upload.json_upload_file),
    url(r'^json/messages_in_narrow$', zerver.views.messages.json_messages_in_narrow),
]
