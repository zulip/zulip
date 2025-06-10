from typing import Any

from django.conf.urls import include
from django.urls import path

from corporate.views.remote_billing_page import remote_realm_billing_entry
from zilencer.auth import remote_server_path
from zilencer.views import (
    deactivate_remote_server,
    register_remote_push_device,
    register_remote_push_device_for_e2ee_push_notification,
    register_remote_server,
    remote_server_check_analytics,
    remote_server_notify_push,
    remote_server_post_analytics,
    remote_server_send_test_notification,
    transfer_remote_server_registration,
    unregister_all_remote_push_devices,
    unregister_remote_push_device,
    verify_registration_transfer_challenge_ack_endpoint,
)

i18n_urlpatterns: Any = []

# Zilencer views following the REST API style
push_bouncer_patterns = [
    remote_server_path("remotes/push/register", POST=register_remote_push_device),
    remote_server_path(
        "remotes/push/e2ee/register", POST=register_remote_push_device_for_e2ee_push_notification
    ),
    remote_server_path("remotes/push/unregister", POST=unregister_remote_push_device),
    remote_server_path("remotes/push/unregister/all", POST=unregister_all_remote_push_devices),
    remote_server_path("remotes/push/notify", POST=remote_server_notify_push),
    remote_server_path("remotes/push/test_notification", POST=remote_server_send_test_notification),
    # Push signup doesn't use the REST API, since there's no auth.
    path("remotes/server/register", register_remote_server),
    path("remotes/server/register/transfer", transfer_remote_server_registration),
    path(
        "remotes/server/register/verify_challenge",
        verify_registration_transfer_challenge_ack_endpoint,
    ),
    remote_server_path("remotes/server/deactivate", POST=deactivate_remote_server),
    # For receiving table data used in analytics and billing
    remote_server_path("remotes/server/analytics", POST=remote_server_post_analytics),
    remote_server_path("remotes/server/analytics/status", GET=remote_server_check_analytics),
]

billing_patterns = [remote_server_path("remotes/server/billing", POST=remote_realm_billing_entry)]

urlpatterns = [
    path("api/v1/", include(push_bouncer_patterns)),
    path("api/v1/", include(billing_patterns)),
]
