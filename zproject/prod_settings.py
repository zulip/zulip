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

################################################################
# Cloudflare R2 Storage (S3-compatible)
################################################################

# NODL MODIFICATION START - Use Cloudflare R2 for file uploads
# Reason: Railway deployments need external storage for persistence
# Date: 2024-12-01
S3_AUTH_UPLOADS_BUCKET = os.environ.get("S3_AUTH_UPLOADS_BUCKET", "")
S3_AVATAR_BUCKET = os.environ.get("S3_AVATAR_BUCKET", "")
S3_REGION = os.environ.get("S3_REGION", "auto")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")

# R2-specific settings
S3_SKIP_CHECKSUM = True  # R2 has limited checksum support
S3_ADDRESSING_STYLE = "path"  # R2 prefers path-style URLs

# Override Zulip's secret-based credentials with env vars
# (Zulip normally uses get_secret() but we use Railway env vars)
S3_KEY = os.environ.get("S3_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
# NODL MODIFICATION END
