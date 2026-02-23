"""Django app registration for nodl extensions."""

NODL_APPS = [
    "nodl.auth.apps.NodlAuthConfig",  # Supabase JWT middleware (uses label 'nodl_auth')
    "nodl.sync",  # User/workspace sync
    "nodl.extensions",  # Extension models
    "nodl.storage",  # R2 storage backend
    "nodl.api",  # Additional REST endpoints
]
