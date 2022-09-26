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

from .configured_settings import *  # noqa: F401,F403 isort: skip
from .computed_settings import *  # noqa: F401,F403 isort: skip

# Do not add any code after these wildcard imports!  Add it to
# computed_settings instead.
