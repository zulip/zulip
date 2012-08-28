import os

# test_settings.py works differently from
# dev_settings.py/prod_settings.py; it actually is directly referenced
# by the test suite as DJANGO_SETTINGS_MODULE and imports settings.py
# directly and then hacks up the values that are different for the
# test suite.  As will be explained, this is kinda messy and probably
# we'd be better off switching it to work more like dev_settings.py,
# but for now, this is what we have.
#
# An important downside of the test_settings.py approach is that if we
# want to change any settings that settings.py then computes
# additional settings from (e.g. EXTERNAL_HOST), we need to do a hack
# like the below line(s) before we import from settings, for
# transmitting the value of EXTERNAL_HOST to dev_settings.py so that
# it can be set there, at the right place in the settings.py flow.
# Ick.
os.environ["EXTERNAL_HOST"] = os.getenv("TEST_EXTERNAL_HOST", "testserver")
os.environ["ZULIP_TEST_SUITE"] = "true"

from .settings import *  # noqa: F403 isort: skip
from .test_extra_settings import *  # noqa: F403 isort: skip

# Do not add any code after these wildcard imports!  Add it to
# test_extra_settings instead.
