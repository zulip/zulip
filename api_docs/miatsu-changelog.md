# Miatsu.co API changelog

The Miatsu.co fork's changes to the upstream Zulip Server API, grouped by
Miatsu.co release (`miatsu_version`). Like Zulip's own
[API changelog](/api/changelog), this is the explicit, client-facing surface
only; the operator-facing release notes live in `docs/miatsu/changelog.md`, and
the conventions behind both are in `docs/miatsu/maintaining-the-fork.md`.

For an API change, the authoritative detail is the `**Changes**` note on the
affected endpoint in `zerver/openapi/zulip.yaml`; entries here are a brief index.
Clients detect Miatsu.co API features via `miatsu_capabilities`, never by
comparing `zulip_feature_level`.

## Miatsu.co 0.1

_Unreleased._ Based on the upstream Zulip 12.x maintenance branch (feature level 499).

- Advertise `miatsu_version` and `miatsu_capabilities` in the `POST /register`
  and `GET /server_settings` responses.
- Add the owner-settable `can_view_user_direct_messages_group` realm setting,
  defaulting to the system "nobody" group. (`PATCH /realm`, `POST /register`,
  `realm`/`update_dict`)
