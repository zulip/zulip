from django.urls import path

from zproject.nodl.views.auth_bridge import auth_bridge
from zproject.nodl.views.calls import (
    accept_call,
    call_detail,
    call_history,
    cancel_call,
    decline_call,
    end_call,
    initiate_call,
)
from zproject.nodl.views.contacts import contacts_match
from zproject.nodl.views.devices import register_voip_token, unregister_voip_token
from zproject.nodl.views.invites import invites_create, invites_list, invites_resend
from zproject.nodl.views.registration_pin import pin_set, pin_verify
from zproject.nodl.views.webhooks_livekit import livekit_webhook

urlpatterns = [
    path("auth/bridge", auth_bridge, name="nodl_auth_bridge"),
    path("pin/set", pin_set, name="nodl_pin_set"),
    path("pin/verify", pin_verify, name="nodl_pin_verify"),
    path("contacts/match", contacts_match, name="nodl_contacts_match"),
    path("invites", invites_list, name="nodl_invites_list"),
    path("invites/create", invites_create, name="nodl_invites_create"),
    path("invites/resend", invites_resend, name="nodl_invites_resend"),
    # Call signaling endpoints
    path("calls/initiate", initiate_call, name="nodl_calls_initiate"),
    path("calls/<str:call_id>/accept", accept_call, name="nodl_calls_accept"),
    path("calls/<str:call_id>/decline", decline_call, name="nodl_calls_decline"),
    path("calls/<str:call_id>/cancel", cancel_call, name="nodl_calls_cancel"),
    path("calls/<str:call_id>/end", end_call, name="nodl_calls_end"),
    # Device VoIP token management
    path("devices/voip-token", register_voip_token, name="nodl_register_voip_token"),
    path("devices/voip-token/unregister", unregister_voip_token, name="nodl_unregister_voip_token"),
    # Call history & detail
    path("calls/history", call_history, name="nodl_calls_history"),
    path("calls/<str:call_id>", call_detail, name="nodl_calls_detail"),
    # Webhooks (no Zulip API key auth — uses LiveKit JWT validation)
    path("webhooks/livekit", livekit_webhook, name="nodl_livekit_webhook"),
]
