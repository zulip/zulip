"""Django app configuration for nodl.auth."""

from django.apps import AppConfig


class NodlAuthConfig(AppConfig):
    """App configuration for nodl authentication module.

    Uses a custom label 'nodl_auth' to avoid conflict with django.contrib.auth.
    """

    name = "nodl.auth"
    label = "nodl_auth"  # Custom label to avoid conflict with django.contrib.auth
    verbose_name = "nodl Authentication"
