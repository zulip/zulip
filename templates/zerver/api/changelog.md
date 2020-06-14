# Changelog

This page documents changes to the Zulip Server API over time.

The recommended way for a client like the Zulip mobile or desktop apps
that needs to support interaction with a wide range of different Zulip
server versions is to check the `zulip_feature_level` parameter in the
`/register` and `/server_settings` responses to determine which of the
below features are supported.

## Changes in Zulip 2.2

**Feature level 12**

* [`GET users/{user_id}/subscriptions/{stream_id}`](/api/get-subscription-status):
  New endpoint added for checking if another user is subscribed to a stream.

**Feature level 11**

* [`POST /register`](/api/register-queue): Added
  `realm_community_topic_editing_limit_seconds` to the response, the
  time limit before community topic editing is forbidden.  A `null`
  value means no limit.
* [`POST /register`](/api/register-queue): The response now contains a
  `is_owner`, similar to the existing `is_admin` and `is_guest` fields.
* [`POST /typing`](/api/typing): Removed legacy support for sending email
  addresses, rather than user IDs, to encode private message recipients.

**Feature level 10**

* [`GET users/me`](/api/get-profile): Added `avatar_version`, `is_guest`,
  `is_active`, `timezone`, and `date_joined` fields to the User objects.
* [`GET users/me`](/api/get-profile): Removed `client_id` and `short_name`
  from the reponse to this endpoint.  These fields had no purpose and
  were inconsistent with other API responses describing users.

**Feature level 9**

* [`POST users/me/subscriptions`](/api/add-subscriptions), [`DELETE
  /users/me/subscriptions`](/api/remove-subscriptions): Other users to
  subscribe/unsubscribe, declared in the `principals` parameter, can
  now be referenced by user_id, rather than Zulip display email
  address.
* [PATCH /messages/{message_id}](/api/update-message): Added
  `send_notification_to_old_thread` and
  `send_notification_to_new_thread` optional parameters.

**Feature level 8**

* [`GET /users`](/api/get-all-users), [`GET /users/{user_id}`](/api/get-user)
  and [`GET /users/me`](/api/get-profile): User objects now contain the
  `is_owner` field as well.

**Feature level 7**

* [`GET /events`](/api/get-events-from-queue): `realm_user` and
  `realm_bot` events no longer contain an `email` field to identify
  the user; use the `user_id` field instead.  Previously, some (but
  not all) events of these types contained an `email` key in addition to
  to `user_id`) for identifying the modified user.
* [`PATCH /users/{user_id}`](/api/update-user): The `is_admin` and
  `is_guest` parameters were removed in favor of the more general
  `role` parameter for specifying a change in user role.
* [`GET /events`](/api/get-events-from-queue): `realm_user` events
  sent when a user's role changes now include `role` property, instead
  of the previous `is_guest` or `is_admin` booleans.
* `GET /realm/emoji`: The user who uploaded a given custom emoji is
  now indicated by an `author_id` field, replacing a previous `author`
  object with unnecessary additional data.

**Feature level 6**

* [`GET /events`](/api/get-events-from-queue): `realm_user` events to
  update a user's avatar now include the `avatar_version` field, which
  is important for correctly refetching medium-size avatar images when
  the user's avatar changes.
* [`GET /users`](/api/get-all-users) and [`GET
  /users/{user_id}`](/api/get-user): User objects now contain the
  `avatar_version` field as well.

**Feature level 5**
* [`GET /events`](/api/get-events-from-queue): `realm_bot` events,
  sent when changes are made to bot users, now contain an
  integer-format `owner_id` field, replacing the `owner` field (which
  was an email address).

**Feature level 4**

* `jitsi_server_url`, `development_environment`, `server_generation`,
  `password_min_length`, `password_min_guesses`, `max_file_upload_size_mib`,
  `max_avatar_file_size_mib`, `server_inline_image_preview`,
  `server_inline_url_embed_preview`, `server_avatar_changes_disabled` and
  `server_name_changes_disabled` fields are now available via
  `POST /register` to make them accessible to all the clients;
  they were only internally available to Zulip's web app prior to this.

**Feature level 3**:

* `zulip_version` and `zulip_feature_level` are always returned
  in `POST /register`; previously they were only returned if `event_types`
  included `zulip_version`.
* Added new `presence_enabled` user notification setting; previously
  [presence](/help/status-and-availability) was always enabled.

**Feature level 2**:

* [`POST /messages/{message_id}/reactions`](/api/add-emoji-reaction):
  The `reaction_type` parameter is optional; the server will guess the
  `reaction_type` if it is not specified (checking custom emoji, then
  unicode emoji for any with the provided name).
* `reactions` objects returned by the API (both in `GET /messages` and
  in `GET /events`) now include the user who reacted in a top-level
  `user_id` field.  The legacy `user` dictionary (which had
  inconsistent format between those two endpoints) is deprecated.

**Feature level 1**:

* [`GET /server_settings`](/api/server-settings): Added
  `zulip_feature_level`, which can be used by clients to detect which
  of the features described in this changelog are supported.
* [`POST /register`](/api/register-queue): Added `zulip_feature_level`
  to the response if `zulip_version` is among the requested
  `event_types`.
* [`GET /users`](/api/get-all-users): User objects for bots now
  contain a `bot_owner_id`, replacing the previous `bot_owner` field
  (which had the email address of the bot owner).
* [`GET /users/{user_id}`](/api/get-user): Endpoint added.
* [`GET /messages`](/api/get-messages): Add support for string-format
  values for the `anchor` parameter, deprecating and replacing the
  `use_first_unread_anchor` parameter.
* [`GET /messages`](/api/get-messages) and [`GET
  /events`](/api/get-events-from-queue): Message objects now use
  `topic_links` rather than `subject_links` to indicate links either
  present in the topic or generated by Linkifiers applied to the topic.
* [`POST /users/me/subscriptions`](/api/add-subscriptions): Replaced
  `is_announcement_only` boolean with `stream_post_policy` enum for
  specifying who can post to a stream.
* [`PATCH /streams/{stream_id}`](/api/update-stream): Replaced
  `is_announcement_only` boolean with `stream_post_policy` enum for
  specifying who can post to a stream.
* [`GET /streams`](/api/get-all-streams): Replaced
  `is_announcement_only` boolean with `stream_post_policy` enum for
  specifying who can post to a stream.
* `GET /api/v1/user_uploads`: Added new endpoint for requesting a
  temporary URL for an uploaded file that does not require
  authentication to access (e.g. for passing from a Zulip desktop,
  mobile, or terminal app to the user's default browser).
* Added `EMAIL_ADDRESS_VISIBILITY_NOBODY` possible value for
  `email_address_visibility`.
* Added `private_message_policy` realm setting.
* `muted_topic` objects now are a 3-item tuple: (`stream_id`, `topic`,
  `date_muted`).  Previously, they were a 2-item tuple.
* `GitLab` authentication is now available.
* Added `None` as a video call provider option.

## Changes in Zulip 2.1

* [`GET /users`](/api/get-all-users): Added `include_custom_profile_fields`
  to request custom profile field data.
* [`GET /users/me`](/api/get-profile): Added `avatar_url` field,
  containing the user's avatar URL, to the response.
* [`GET /users/me/subscriptions`](/api/get-subscribed-streams): Added
  `include_subscribers` parameter controlling whether data on the
  other subscribers is included.  Previous behavior was to always send
  subscriber data.
* [`GET /users/me/subscriptions`](/api/get-subscribed-streams):
  Stream-level notification settings like `push_notifications` were
  changed to be nullable boolean fields (true/false/null), with `null`
  meaning that the stream inherits the organization-level default.
  Previously, the only values were true/false.  A client communicates
  support for this feature using `client_capabilities`.
* [`GET /users/me/subscriptions`](/api/get-subscribed-streams): Added
  `wildcard_mentions_notify` notification setting, with the same
  global-plus-stream-level-override model as other notification settings.
* [`GET /server_settings`](/api/server-settings): Added
  `external_authentication_methods` structure, used to display login
  buttons nicely in the mobile apps.
* Added `first_message_id` field to Stream objects.  This is helpful
  for determining whether the stream has any messages older than a
  window cached in a client.
* Added `is_web_public` field to Stream objects.  This field is
  intended to support web-public streams.
* Added `/export/realm` endpoints for triggering a data export.
* `PATCH /realm`: Added `invite_to_stream_policy`,
  `create_stream_policy`, `digest_emails_enabled`, `digest_weekday`,
  `user_group_edit_policy`, and `avatar_changes_disabled` organization settings.
* Added `fluid_layout_width`, `desktop_icon_count_display`, and
  `demote_inactive_streams` display settings.
* `enable_stream_sounds` was renamed to
  `enable_stream_audible_notifications`.
* Deprecated `is_home_view`, replacing it with the more readable
  `is_muted` (with the opposite meaning).
* Custom profile fields: Added `EXTERNAL_ACCOUNT` field type.

## Changes in Zulip 2.0

* [`POST /messages`](/api/send-message): Added support for using user
  IDs and stream IDs for specifying the recipients of a message.
* [`POST /typing`](/api/typing): Added support for specifying the
  recipients with user IDs, deprecating the original API of specifying
  them using email addresses.

------------------

## Changes not yet stabilized

* [`POST /register`](/api/register-queue): Added `slim_presence`
  parameter.  Changes the format of presence events, but is still
  being changed and should not be used by clients.
* `message_retention_days` field in stream objects.
