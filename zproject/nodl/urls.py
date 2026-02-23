from django.urls import path

from zproject.nodl.views.auth_bridge import auth_bridge

urlpatterns = [
    path("auth/bridge", auth_bridge, name="nodl_auth_bridge"),
]
