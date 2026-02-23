from django.urls import path

from zproject.nodl.views.auth_bridge import auth_bridge
from zproject.nodl.views.contacts import contacts_match
from zproject.nodl.views.invites import invites_create, invites_list, invites_resend
from zproject.nodl.views.registration_pin import pin_set, pin_verify

urlpatterns = [
    path("auth/bridge", auth_bridge, name="nodl_auth_bridge"),
    path("pin/set", pin_set, name="nodl_pin_set"),
    path("pin/verify", pin_verify, name="nodl_pin_verify"),
    path("contacts/match", contacts_match, name="nodl_contacts_match"),
    path("invites", invites_list, name="nodl_invites_list"),
    path("invites/create", invites_create, name="nodl_invites_create"),
    path("invites/resend", invites_resend, name="nodl_invites_resend"),
]
