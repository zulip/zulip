"""MiAtSu.Co fork-specific version and capability constants.

See docs/contributing/miatsuco-fork-conventions.md for the full convention
this module exists to support.
"""

# Human-facing release version of this fork, independent of ZULIP_VERSION.
# Advertised to clients as ``miatsuco_version``. Bump this when cutting a
# fork release; never derive it from or tie it to ZULIP_VERSION.
MIATSUCO_VERSION = "0.1-dev"

# Named capability flags advertised to clients as ``miatsuco_capabilities``
# in the POST /register and GET /server_settings responses. Each entry
# marks a fork feature that a client can detect by name and gate its own
# behavior on, rather than by comparing zulip_feature_level or assuming a
# feature exists based on miatsuco_version alone (a client should not need
# to maintain its own version-to-feature mapping).
#
# Add a flag in the same commit that makes the corresponding feature usable
# end to end (not in an earlier scaffolding commit), so the flag never
# advertises a feature that doesn't actually work yet. Once shipped, treat
# a capability name as a stable public API: don't rename or remove it
# without a deprecation path, since a client may already be checking for it.
MIATSUCO_CAPABILITIES: list[str] = []
