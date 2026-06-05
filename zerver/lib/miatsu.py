"""Miatsu.co fork-specific version and capability constants.

Miatsu.co is a downstream fork of Zulip that periodically merges upstream
releases without being reabsorbed upstream. To keep those merges clean and
avoid colliding with upstream's version signals, all fork-owned version and
capability state lives here rather than in ``version.py`` (which is owned by
upstream and is updated only when merging a new Zulip release).

See ``docs/miatsu/maintaining-the-fork.md`` for the full conventions.
"""

# Human-facing release version of the Miatsu.co fork, independent of
# ZULIP_VERSION. Advertised to clients as ``miatsu_version`` and used to head
# the sections of api_docs/miatsu-changelog.md.
MIATSU_VERSION = "0.1-dev"

# Named capability flags advertised to clients as ``miatsu_capabilities`` in
# the POST /register and GET /server_settings responses. Each entry marks an API
# or behavior change Miatsu.co makes, so that clients detect fork features by
# name and never by comparing Zulip's upstream ``zulip_feature_level`` (which
# would collide when a newer upstream release is merged in). Add a flag in the
# same commit that makes the corresponding feature usable end to end, and record
# it in api_docs/miatsu-changelog.md.
MIATSU_CAPABILITIES: list[str] = []
