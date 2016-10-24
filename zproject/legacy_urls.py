from django.conf.urls import url

# Future endpoints should add to urls.py, which includes these legacy urls

legacy_urls = [
    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/make_stream_public$',       'zerver.views.streams.json_make_stream_public'),
    url(r'^json/make_stream_private$',      'zerver.views.streams.json_make_stream_private'),
    url(r'^json/invite_users$',             'zerver.views.invite.json_invite_users'),
    url(r'^json/bulk_invite_users$',        'zerver.views.invite.json_bulk_invite_users'),
    url(r'^json/refer_friend$',             'zerver.views.invite.json_refer_friend'),
    url(r'^json/settings/change$',          'zerver.views.user_settings.json_change_settings'),
    url(r'^json/notify_settings/change$',   'zerver.views.user_settings.json_change_notify_settings'),
    url(r'^json/ui_settings/change$',       'zerver.views.user_settings.json_change_ui_settings'),
    url(r'^json/subscriptions/remove$',     'zerver.views.streams.json_remove_subscriptions'),

    # We should remove this endpoint and all code related to it.
    # It returns a 404 if the stream doesn't exist, which is confusing
    # for devs, and I don't think we need to go to the server
    # any more to find out about subscriptions, since they are already
    # pushed to us via the event system.
    url(r'^json/subscriptions/exists$',     'zerver.views.streams.json_stream_exists'),

    url(r'^json/subscriptions/property$',   'zerver.views.streams.json_subscription_property'),
    url(r'^json/get_subscribers$',          'zerver.views.streams.json_get_subscribers'),
    url(r'^json/fetch_api_key$',            'zerver.views.auth.json_fetch_api_key'),
    url(r'^json/tutorial_send_message$',    'zerver.views.tutorial.json_tutorial_send_message'),
    url(r'^json/tutorial_status$',          'zerver.views.tutorial.json_tutorial_status'),
    url(r'^json/report_error$',             'zerver.views.report.json_report_error'),
    url(r'^json/report_send_time$',         'zerver.views.report.json_report_send_time'),
    url(r'^json/report_narrow_time$',       'zerver.views.report.json_report_narrow_time'),
    url(r'^json/report_unnarrow_time$',     'zerver.views.report.json_report_unnarrow_time'),
    url(r'^json/upload_file$',              'zerver.views.upload.json_upload_file'),
    url(r'^json/messages_in_narrow$',       'zerver.views.messages.json_messages_in_narrow'),
    url(r'^json/update_message$',           'zerver.views.messages.json_update_message'),
    url(r'^json/fetch_raw_message$',        'zerver.views.messages.json_fetch_raw_message'),
    url(r'^json/set_muted_topics$',         'zerver.views.json_set_muted_topics'),
    url(r'^json/set_avatar$',               'zerver.views.user_settings.json_set_avatar'),
    url(r'^json/time_setting$',             'zerver.views.user_settings.json_time_setting'),
    url(r'^json/left_side_userlist$',       'zerver.views.user_settings.json_left_side_userlist'),
    url(r'^json/language_setting$',         'zerver.views.user_settings.json_language_setting'),
]
