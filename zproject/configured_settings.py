########################################################################
# DEFAULT VALUES FOR SETTINGS
########################################################################

# For any settings that are not set in the site-specific configuration file
# (/etc/zulip/settings.py in production, or dev_settings.py or test_settings.py
# in dev and test), we want to initialize them to sane defaults.
from .default_settings import *  # noqa: F403 isort: skip

# Import variables like secrets from the prod_settings file
# Import prod_settings after determining the deployment/machine type
from .config import PRODUCTION

if PRODUCTION:  # nocoverage
    from .prod_settings import *  # noqa: F403 isort: skip
else:
    # For the Dev VM environment, we use the same settings as the
    # sample prod_settings.py file, with a few exceptions.
    from .prod_settings_template import *  # noqa: F403 isort: skip
    from .dev_settings import *  # noqa: F403 isort: skip

# Do not add any code after these wildcard imports!  Add it to
# computed_settings instead.
