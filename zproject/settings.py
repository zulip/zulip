# Django settings for zulip project.
########################################################################
# Here's how settings for the Zulip project work:
#
# * configured_settings.py imports default_settings.py, which contains
#   default values for settings configurable in prod_settings.py.
#
# * configured_settings.py imports prod_settings.py, and any site-specific
#   configuration belongs there.  The template for prod_settings.py is
#   prod_settings_template.py.
#
# * computed_settings.py contains non-site-specific and settings
#   configuration for the Zulip Django app.
#
# See https://zulip.readthedocs.io/en/latest/subsystems/settings.html for more information
#
########################################################################
from typing import TYPE_CHECKING

# Monkey-patch certain types that are declared as generic types
# generic in django-stubs, but not (yet) as generic types in Django
# itself. This is necessary to ensure type references like
# django.db.models.Lookup[int] work correctly at runtime.
#
# Hide this from mypy to avoid creating stupid cycles like
# zproject.settings → django_stubs_ext → django_stubs_ext.patch →
# django.contrib.admin.options → django.contrib.contenttypes.models →
# confirmation.models → django.conf → zproject.settings.
if not TYPE_CHECKING:
    import django_stubs_ext

    django_stubs_ext.monkeypatch()

from .configured_settings import *  # noqa: F403 isort: skip
from .computed_settings import *  # noqa: F403 isort: skip

# Do not add any code after these wildcard imports!  Add it to
# computed_settings instead.
