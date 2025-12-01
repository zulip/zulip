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

################################################################
# Authentication - Supabase JWT only (no email/password)
################################################################

# NODL MODIFICATION START - Use Supabase auth backend
# Reason: Replace Zulip's email/password auth with Supabase JWT
# Date: 2024-12-01
# See: architecture/chat-architecture.md, Story 1.2
AUTHENTICATION_BACKENDS: tuple[str, ...] = (
    "nodl.auth.backends.SupabaseAuthBackend",
)
# NODL MODIFICATION END
