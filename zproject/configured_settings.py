########################################################################
# DEFAULT VALUES FOR SETTINGS
########################################################################

import os

# For any settings that are not set in the site-specific configuration file
# (/etc/zulip/settings.py in production, or dev_settings.py or test_settings.py
# in dev and test), we want to initialize them to sane defaults.
from .default_settings import *  # noqa: F403 isort: skip

# Import variables like secrets from the prod_settings file
# Import prod_settings after determining the deployment/machine type
from .config import PRODUCTION

TEST_SUITE = os.getenv("ZULIP_TEST_SUITE") == "true"
CUSTOM_DEVELOPMENT_SETTINGS = False

if PRODUCTION:  # nocoverage
    from .prod_settings import *  # noqa: F403 isort: skip
else:
    # For the Dev VM environment, we use the same settings as the
    # sample prod_settings.py file, with a few exceptions.
    from .prod_settings_template import *  # noqa: F403 isort: skip
    from .dev_settings import *  # noqa: F403 isort: skip

    # Support for local overrides to dev_settings.py is implemented here.
    #
    # We're careful to avoid those overrides applying to automated tests.
    if not TEST_SUITE:  # nocoverage
        import contextlib

        with contextlib.suppress(ImportError):
            from zproject.custom_dev_settings import *  # type: ignore[import, unused-ignore] # noqa: F403

            # Track that we've got settings changes, so you know if
            # you're testing non-base code; runtornado will log.
            CUSTOM_DEVELOPMENT_SETTINGS = True

# Do not add any code after these wildcard imports!  Add it to
# computed_settings instead.
