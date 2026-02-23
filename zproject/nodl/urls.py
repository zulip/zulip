from django.urls import path

from zproject.nodl.views.auth_bridge import auth_bridge
from zproject.nodl.views.registration_pin import pin_set, pin_verify

urlpatterns = [
    path("auth/bridge", auth_bridge, name="nodl_auth_bridge"),
    path("pin/set", pin_set, name="nodl_pin_set"),
    path("pin/verify", pin_verify, name="nodl_pin_verify"),
]
