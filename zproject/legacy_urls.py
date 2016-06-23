from django.conf import settings
from django.conf.urls import patterns, url, include
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import TemplateView, RedirectView
from django.utils.module_loading import import_string
import os.path
import zerver.forms

# Future endpoints should add to urls.py, which includes these legacy urls

legacy_urls = [
    # These are json format views used by the web client.  They require a logged in browser.
    url(r'^json/rename_stream$',            'zerver.views.streams.json_rename_stream'),
    url(r'^json/make_stream_public$',       'zerver.views.streams.json_make_stream_public'),
    url(r'^json/make_stream_private$',      'zerver.views.streams.json_make_stream_private'),
    url(r'^json/invite_users$',             'zerver.views.json_invite_users'),
    url(r'^json/bulk_invite_users$',        'zerver.views.json_bulk_invite_users'),
    url(r'^json/settings/change$',          'zerver.views.user_settings.json_change_settings'),
    url(r'^json/notify_settings/change$',   'zerver.views.user_settings.json_change_notify_settings'),
    url(r'^json/ui_settings/change$',       'zerver.views.user_settings.json_change_ui_settings'),
    url(r'^json/subscriptions/remove$',     'zerver.views.streams.json_remove_subscriptions'),
    url(r'^json/subscriptions/exists$',     'zerver.views.streams.json_stream_exists'),
    url(r'^json/subscriptions/property$',   'zerver.views.streams.json_subscription_property'),
    url(r'^json/get_subscribers$',          'zerver.views.streams.json_get_subscribers'),
    url(r'^json/fetch_api_key$',            'zerver.views.json_fetch_api_key'),
    url(r'^json/get_active_statuses$',      'zerver.views.json_get_active_statuses'),
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
    url(r'^json/refer_friend$',             'zerver.views.json_refer_friend'),
    url(r'^json/set_muted_topics$',         'zerver.views.json_set_muted_topics'),
    url(r'^json/set_avatar$',               'zerver.views.user_settings.json_set_avatar'),
    url(r'^json/time_setting$',             'zerver.views.user_settings.json_time_setting'),
    url(r'^json/left_side_userlist$',       'zerver.views.user_settings.json_left_side_userlist'),

    # This json format view is used by the LEGACY pre-REST API.  It
    # requires an API key.
    url(r'^api/v1/send_message$',           'zerver.views.messages.api_send_message'),

    # This json format view used by the mobile apps accepts a username
    # password/pair and returns an API key.
    url(r'^api/v1/fetch_api_key$',          'zerver.views.api_fetch_api_key'),

    # This is for the signing in through the devAuthBackEnd on mobile apps.
    url(r'^api/v1/dev_fetch_api_key$',      'zerver.views.api_dev_fetch_api_key'),
    # This is for fetching the emails of the admins and the users.
    url(r'^api/v1/dev_get_emails$',         'zerver.views.api_dev_get_emails'),

    # Used to present the GOOGLE_CLIENT_ID to mobile apps
    url(r'^api/v1/fetch_google_client_id$', 'zerver.views.api_fetch_google_client_id'),

    # Sorted integration-specific webhook callbacks.
    url(r'^api/v1/external/airbrake$',      'zerver.views.webhooks.airbrake.api_airbrake_webhook'),
    url(r'^api/v1/external/beanstalk$',     'zerver.views.webhooks.beanstalk.api_beanstalk_webhook'),
    url(r'^api/v1/external/bitbucket$',     'zerver.views.webhooks.bitbucket.api_bitbucket_webhook'),
    url(r'^api/v1/external/circleci$',      'zerver.views.webhooks.circleci.api_circleci_webhook'),
    url(r'^api/v1/external/codeship$',      'zerver.views.webhooks.codeship.api_codeship_webhook'),
    url(r'^api/v1/external/crashlytics$',   'zerver.views.webhooks.crashlytics.api_crashlytics_webhook'),
    url(r'^api/v1/external/desk$',          'zerver.views.webhooks.deskdotcom.api_deskdotcom_webhook'),
    url(r'^api/v1/external/freshdesk$',     'zerver.views.webhooks.freshdesk.api_freshdesk_webhook'),
    url(r'^api/v1/external/github$',        'zerver.views.webhooks.github.api_github_landing'),
    url(r'^api/v1/external/ifttt$',         'zerver.views.webhooks.ifttt.api_iftt_app_webhook'),
    url(r'^api/v1/external/jira$',          'zerver.views.webhooks.jira.api_jira_webhook'),
    url(r'^api/v1/external/newrelic$',      'zerver.views.webhooks.newrelic.api_newrelic_webhook'),
    url(r'^api/v1/external/pagerduty$',     'zerver.views.webhooks.pagerduty.api_pagerduty_webhook'),
    url(r'^api/v1/external/pingdom$',       'zerver.views.webhooks.pingdom.api_pingdom_webhook'),
    url(r'^api/v1/external/pivotal$',       'zerver.views.webhooks.pivotal.api_pivotal_webhook'),
    url(r'^api/v1/external/stash$',         'zerver.views.webhooks.stash.api_stash_webhook'),
    url(r'^api/v1/external/taiga$',         'zerver.views.webhooks.taiga.api_taiga_webhook'),
    url(r'^api/v1/external/teamcity$',      'zerver.views.webhooks.teamcity.api_teamcity_webhook'),
    url(r'^api/v1/external/transifex$',     'zerver.views.webhooks.transifex.api_transifex_webhook'),
    url(r'^api/v1/external/travis$',        'zerver.views.webhooks.travis.api_travis_webhook'),
    url(r'^api/v1/external/updown$',        'zerver.views.webhooks.updown.api_updown_webhook'),
    url(r'^api/v1/external/yo$',            'zerver.views.webhooks.yo.api_yo_app_webhook'),
    url(r'^api/v1/external/zendesk$',       'zerver.views.webhooks.zendesk.api_zendesk_webhook'),

    url(r'^user_uploads/(?P<realm_id_str>(\d*|unk))/(?P<filename>.*)', 'zerver.views.upload.get_uploaded_file'),
]
