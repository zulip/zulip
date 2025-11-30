import os

################################################################
# Mandatory settings - read from environment variables
################################################################

EXTERNAL_HOST = os.environ.get("EXTERNAL_HOST", "localhost")
ZULIP_ADMINISTRATOR = os.environ.get("ZULIP_ADMINISTRATOR", "admin@localhost")

# Allow Railway's domain and any custom domains
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
