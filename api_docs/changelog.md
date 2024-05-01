# API changelog

This page documents changes to the Zulip Server API over time. See
also the [Zulip release lifecycle][release-lifecycle] for background
on why this API changelog is important, and the [Zulip server
changelog][server-changelog].

The API feature levels system used in this changelog is designed to
make it possible to write API clients, such as the Zulip mobile and
terminal apps, that work with a wide range of Zulip server
versions. Every change to the Zulip API is recorded briefly here and
with full details in **Changes** entries in the API documentation for
the modified endpoint(s).

When using an API endpoint whose behavior has changed, Zulip API
clients should check the `zulip_feature_level` field, present in the
[`GET /server_settings`](/api/get-server-settings) and [`POST
/register`](/api/register-queue) responses, to determine the API
format used by the Zulip server that they are interacting with.

## Changes in Zulip 9.0

**Feature level 256**

* [`GET /events`](/api/get-events): Stream update events with a new
  `first_message_id` may now be sent when messages are deleted.

**Feature level 255**

* "Stream" was renamed to "Channel" across strings in the Zulip API
  and UI. Clients supporting a range of server versions are encouraged
  to use different strings based on the server's API feature level for
  consistency. Note that feature level marks the strings transition
  only: Actual API changes related to this transition have their own
  API changelog entries.

**Feature level 254**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`GET /streams`](/api/get-streams),
  [`GET /streams/{stream_id}`](/api/get-stream-by-id),
  [`GET /users/me/subscriptions`](/api/get-subscriptions): Added a new
  field `creator_id` to stream and subscription objects, which contains the
  user ID of the stream's creator.

**Feature level 253**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults),
  [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings):
  Added new `receives_typing_notifications` option to allow users to decide whether
  to receive typing notification events from other users.

**Feature level 252**

* `PATCH /realm/profile_fields/{field_id}`: `name`, `hint`, `display_in_profile_summary`,
  `required` and `field_data` fields are now optional during an update. Previously we
  required the clients to populate the fields in the PATCH request even if there was
  no change to those fields' values.

**Feature level 251**

* [`POST /register`](/api/register-queue): Fixed `realm_upload_quota_mib`
  value to actually be in MiB. Until now the value was in bytes.

**Feature level 250**

* [`GET /messages`](/api/get-messages),
  [`GET /messages/matches_narrow`](/api/check-messages-match-narrow),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow),
  [`POST /register`](/api/register-queue):
  Added support for two [search/narrow filters](/api/construct-narrow)
  related to stream messages: `channel` and `channels`. The `channel`
  operator is an alias for the `stream` operator. The `channels`
  operator is an alias for the `streams` operator.

**Feature level 249**

* [`GET /messages`](/api/get-messages),
  [`GET /messages/matches_narrow`](/api/check-messages-match-narrow),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow),
  [`POST /register`](/api/register-queue):
  Added support for a new [search/narrow filter](/api/construct-narrow),
  `has:reaction`, which returns messages with at least one [emoji
  reaction](/help/emoji-reactions).

**Feature level 248**

* [`POST /typing`](/api/set-typing-status), [`POST /messages`](/api/send-message),
  [`POST /scheduled_messages`](/api/create-scheduled-message),
  [`PATCH /scheduled_messages/<int:scheduled_message_id>`](/api/update-scheduled-message):
  Added `"channel"` as an additional value for the `type` parameter to
  indicate a stream message.

**Feature level 247**

* [Markdown message formatting](/api/message-formatting#mentions):
  Added `channel` to the supported options for [wildcard
  mentions](/help/mention-a-user-or-group#mention-everyone-on-a-stream).

**Feature level 246**

* [`POST /register`](/api/register-queue), [`POST
  /events`](/api/get-events): Added new `require_unique_names` setting
  controlling whether users names can duplicate others.

**Feature level 245**

* [`PATCH
  /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults)
  [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events), [`PATCH
  /settings`](/api/update-settings): Added new `web_font_size_px` and
  `web_line_height_percent` settings to allow users to control the
  styling of the web application.

**Feature level 244**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`POST /realm/profile_fields`](/api/create-custom-profile-field),
  [`GET /realm/profile_fields`](/api/get-custom-profile-fields): Added a new
  parameter `required`, on custom profile field objects, indicating whether an
  organization administrator has configured the field as something users should
  be required to provide.

**Feature level 243**

* [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events): Changed the format of
  `realm_authentication_methods` and `authentication_methods`,
  respectively, to use a dictionary rather than a boolean as the value
  for each authentication method. The new dictionaries are more
  extensively and contain fields indicating whether the backend is
  unavailable to the current realm due to Zulip Cloud plan
  restrictions or any other reason.

**Feature level 242**

* [`POST /register`](/api/register-queue), [`POST /events`](/api/get-events),
  `PATCH /realm`: Added `zulip_update_announcements_stream_id` realm setting,
  which is the ID of the of the stream to which automated messages announcing
  new features or other end-user updates about the Zulip software are sent.

**Feature level 241**

* [`POST /register`](/api/register-queue), [`POST /events`](/api/get-events),
  `PATCH /realm`: Renamed the realm settings `notifications_stream` and
  `signup_notifications_stream` to `new_stream_announcements_stream` and
  `signup_announcements_stream`, respectively.

**Feature level 240**

* [`GET /events`](/api/get-events): The `restart` event no longer contains an
  optional `immediate` flag.
* [`GET /events`](/api/get-events): A new `web_reload_client` event has been
  added; it is used to signal to website-based clients that they should reload
  their code.  This was previously implied by the `restart` event.

Feature levels 238-239 are reserved for future use in 8.x maintenance
releases.

## Changes in Zulip 8.0

**Feature level 237**

No changes; feature level used for Zulip 8.0 release.

**Feature level 236**

* [`POST /messages`](/api/send-message), [`POST
  /scheduled_messages`](/api/create-scheduled-message): The new
  `read_by_sender` parameter lets the client override the heuristic
  that determines whether the new message will be initially marked
  read by its sender.

**Feature level 235**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults),
  [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings):
  Added a new user setting, `automatically_follow_topics_where_mentioned`,
  that allows the user to automatically follow topics where the user is mentioned.

**Feature level 234**

* Mobile push notifications now include a `realm_name` field.
* [`POST /mobile_push/test_notification`](/api/test-notify) now sends
  a test notification with `test` rather than `test-by-device-token`
  in the `event` field.

**Feature level 233**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events):
  Renamed the `hotspots` event type and the related `hotspots` object array
  to `onboarding_steps`. These are sent to clients if there are onboarding
  steps to display to the user. Onboarding steps now include
  both hotspots and one-time notices. Prior to this, hotspots were the only
  type of onboarding step. Also, added a `type` field to the objects
  returned in the renamed `onboarding_steps` array to distinguish between
  the two types of onboarding steps.

* `POST /users/me/onboarding_steps`: Added a new endpoint, which
  deprecates the `/users/me/hotspots` endpoint, in order to support
  displaying both one-time notices (which highlight new features for
  existing users) and hotspots (which are used in new user tutorials).
  This endpoint marks both types of onboarding steps, i.e. `hotspot`
  and `one_time_notice`, as read by the user. There is no compatibility
  support for `/users/me/hotspots` as no client other than the Zulip
  web app used the endpoint prior to these changes.

**Feature level 232**

* [`POST /register`](/api/register-queue): Added a new
  `user_list_incomplete` [client
  capability](/api/register-queue#parameter-client_capabilities)
  controlling whether `realm_users` contains "Unknown user"
  placeholder objects for users that the current user cannot access
  due to a `can_access_all_users_group` policy.

* [`GET /events`](/api/get-events): The new `user_list_incomplete`
  [client
  capability](/api/register-queue#parameter-client_capabilities)
  controls whether to send `realm_user` events with `op: "add"`
  containing "Unknown user" placeholder objects to clients when a new
  user is created that the client does not have access to due to a
  `can_access_all_users_group` policy.

**Feature level 231**

* [`POST /register`](/api/register-queue):
  `realm_push_notifications_enabled` now represents more accurately
  whether push notifications are actually enabled via the mobile push
  notifications service. Added
  `realm_push_notifications_enabled_end_timestamp` field to realm
  data.

* [`GET /events`](/api/get-events): A `realm` update event is now sent
  whenever `push_notifications_enabled` or
  `push_notifications_enabled_end_timestamp` changes.

**Feature level 230**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events):
  Added `has_trigger` field to objects returned in the `hotspots` array to
  identify if the hotspot will activate only when some specific event
  occurs.

**Feature level 229**

* [`PATCH /messages/{message_id}`](/api/update-message), [`POST
  /messages`](/api/send-message): Topic wildcard mentions involving
  large numbers of participants are now restricted by
  `wildcard_mention_policy`. The server now uses the
  `STREAM_WILDCARD_MENTION_NOT_ALLOWED` and
  `TOPIC_WILDCARD_MENTION_NOT_ALLOWED` error codes when a message is
  rejected because of `wildcard_mention_policy`.

**Feature level 228**

* [`GET /events`](/api/get-events): `realm_user` events with `op: "update"`
  are now only sent to users who can access the modified user.

* [`GET /events`](/api/get-events): `presence` events are now only sent to
  users who can access the user who comes back online if the
  `CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE` server setting is set
  to `true`.

* [`GET /events`](/api/get-events): `user_status` events are now only
  sent to users who can access the modified user.

* [`GET /realm/presence`](/api/get-presence): The endpoint now returns
  presence information of accessible users only if the
  `CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE` server setting is set
  to `true`.

* [`GET /events`](/api/get-events): `realm_user` events with `op: "add"`
  are now also sent when a guest user gains access to a user.

* [`GET /events`](/api/get-events): `realm_user` events with `op: "remove"`
  are now also sent when a guest user loses access to a user.

**Feature level 227**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults),
  [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings):
  Added `DMs, mentions, and followed topics` option for `desktop_icon_count_display`
  setting, and renumbered the options.
  The total unread count of DMs, mentions, and followed topics appears in
  desktop sidebar and browser tab when this option is configured.

**Feature level 226**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`GET /users/me/subscriptions`](/api/get-subscriptions): Removed
  `email_address` field from subscription objects.

* [`GET /streams/{stream_id}/email_address`](/api/get-stream-email-address):
  Added new endpoint to get email address of a stream.

**Feature level 225**

* `PATCH /realm`, [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events): Added `can_access_all_users_group_id`
  realm setting, which is the ID of the user group whose members can
  access all the users in the oragnization.

* [`POST /register`](/api/register-queue): Added `allowed_system_groups`
  field to configuration data object of permission settings passed in
  `server_supported_permission_settings`.

**Feature level 224**

* [`GET /events`](/api/get-events), [`GET /messages`](/api/get-messages),
  [`GET /messages/{message_id}`](/api/get-message): Of the [available
  message flags](/api/update-message-flags#available-flags) that a user
  may have for a message, the `wildcard_mentioned` flag was
  deprecated in favor of the `stream_wildcard_mentioned` and
  `topic_wildcard_mentioned` flags, but it is still available for
  backwards compatibility.

**Feature level 223**

* `POST /users/me/apns_device_token`:
  The `appid` parameter is now required.
  Previously it defaulted to the server setting `ZULIP_IOS_APP_ID`,
  defaulting to "org.zulip.Zulip".

* `POST /remotes/server/register`: The `ios_app_id` parameter is now
  required when `kind` is 1, i.e. when registering an APNs token.
  Previously it was ignored, and the push bouncer effectively
  assumed its value was the server setting `APNS_TOPIC`,
  defaulting to "org.zulip.Zulip".

**Feature level 222**

* [`GET /events`](/api/get-events): When a user is deactivated or
  reactivated, the server uses `realm_user` events with `op: "update"`
  updating the `is_active` field, instead of `realm_user` events with
  `op: "remove"` and `op: "add"`, respectively.

* [`GET /events`](/api/get-events): When a bot is deactivated or
  reactivated, the server sends `realm_bot` events with `op: "update"`
  updating the `is_active` field, instead of `realm_bot` events with
  `op: "remove"` and `op: "add"`, respectively.

**Feature level 221**

* [`POST /register`](/api/register-queue): Added `server_supported_permission_settings`
  field in the response which contains configuration data for various permission
  settings.

**Feature level 220**

* [`GET /events`](/api/get-events): Stream creation events for web-public
  streams are now sent to all guest users in the organization as well.

* [`GET /events`](/api/get-events): The `subscription` events for `op:
  "peer_add"` and `op: "peer_remove"` are now sent to subscribed guest
  users for public streams and to all the guest users for web-public
  streams; previously, they incorrectly only received these for
  private streams.

**Feature level 219**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults)
  [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`PATCH /settings`](/api/update-settings): Renamed `default_view` and
  `escape_navigates_to_default_view` settings to `web_home_view` and
  `web_escape_navigates_to_home_view` respectively.
* [`POST /user_topics`](/api/update-user-topic), [`POST
  register`](/api/register-queue), [`GET /events`](/api/get-events):
  Added followed as a supported value for visibility policies in
  `user_topic` objects.

**Feature level 218**

* [`POST /messages`](/api/send-message): Added an optional
  `automatic_new_visibility_policy` enum field in the success response
  to indicate the new visibility policy value due to the [visibility policy settings](/help/mute-a-topic)
  during the send message action.

**Feature level 217**

* [`POST /mobile_push/test_notification`](/api/test-notify): Added new endpoint
  to send a test push notification to a mobile device or devices.

**Feature level 216**:

* `PATCH /realm`, [`POST register`](/api/register-queue),
  [`GET /events`](/api/get-events): Added `enable_guest_user_indicator`
  setting to control whether "(guest)" is added to user names in UI.

**Feature level 215**

* [`GET /events`](/api/get-events): Replaced the value `private`
  with `direct` in the `message_type` field for the `typing` events
  sent when a user starts or stops typing a message.

* [`POST /typing`](/api/set-typing-status): Stopped supporting `private`
  as a valid value for the `type` parameter.

* [`POST /typing`](/api/set-typing-status): Stopped using the `to` parameter
  for the `"stream"` type. Previously, in the case of the `"stream"` type, it
  accepted a single-element list containing the ID of the stream. Added an
  optional parameter, `stream_id`. Now, `to` is used only for `"direct"` type.
  In the case of `"stream"` type, `stream_id` and `topic` are used.

* Note that stream typing notifications were not enabled in any Zulip client
  prior to feature level 215.

**Feature level 214**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults),
  [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings):
  Added two new user settings, `automatically_follow_topics_policy` and
  `automatically_unmute_topics_in_muted_streams_policy`. The settings control the
  user's preference on which topics the user will automatically 'follow' and
  'unmute in muted streams' respectively.

**Feature level 213**

* [`POST /register`](/api/register-queue): Fixed incorrect handling of
  unmuted and followed topics in calculating the `mentions` and
  `count` fields of the `unread_msgs` object.

**Feature level 212**

* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue),
  `PATCH /realm`: Added the `jitsi_server_url` field to the `realm` object,
  allowing organizations to set a custom Jitsi Meet server. Previously, this
  was only available as a server-level configuration.

* [`POST /register`](/api/register-queue): Added `server_jitsi_server_url`
  fields to the `realm` object. The existing `jitsi_server_url` will now be
  calculated as `realm_jitsi_server_url || server_jitsi_server_url`.

**Feature level 211**

* [`POST /streams/{stream_id}/delete_topic`](/api/delete-topic),
  [`POST /mark_all_as_read`](/api/mark-all-as-read):
  Added a `complete` boolean field in the success response to indicate
  whether all or only some of the targeted messages were processed.
  This replaces the use of `"result": "partially_completed"` (introduced
  in feature levels 154 and 153), so that these endpoints now send a
  `result` string of either `"success"` or `"error"`, like the rest of
  the Zulip API.

**Feature level 210**

* [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings),
  [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added new `web_stream_unreads_count_display_policy` display setting, which controls in
  which streams (all/unmuted/none) unread messages count shows up
  in left sidebar.

**Feature level 209**

* `PATCH /realm`, [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events): Added `create_multiuse_invite_group`
  realm setting, which is the ID of the user group whose members can
  create [reusable invitation links](/help/invite-new-users#create-a-reusable-invitation-link)
  to an organization. Previously, only admin users could create these
  links.

* [`POST /invites/multiuse`](/api/create-invite-link): Non-admin users can
  now use this endpoint to create reusable invitation links. Previously,
  this endpoint was restricted to admin users only.

* [`GET /invites`](/api/get-invites): Endpoint response for non-admin users now
  includes both email invitations and reusable invitation links that they have
  created. Previously, non-admin users could only create email invitations, and
  therefore the response did not include reusable invitation links for these
  users.

* `DELETE /invites/multiuse/{invite_id}`: Non-admin users can now revoke
  reusable invitation links they have created. Previously, only admin users could
  create and revoke reusable invitation links.

* [`GET /events`](/api/get-events): When the set of invitations in an
  organization changes, an `invites_changed` event is now sent to the
  creator of the changed invitation, as well as all admin users.
  Previously, this event was only sent to admin users.

**Feature level 208**

* [`POST /users/me/subscriptions`](/api/subscribe),
  [`DELETE /users/me/subscriptions`](/api/unsubscribe): These endpoints
  now return an HTTP status code of 400 with `code: "BAD_REQUEST"` in
  the error response when a user specified in the `principals` parameter
  is deactivated or does not exist. Previously, these endpoints returned
  an HTTP status code of 403 with `code: "UNAUTHORIZED_PRINCIPAL"` in the
  error response for these cases.

**Feature level 207**

* [`POST /register`](/api/register-queue): Added `display_name` and
  `all_event_types` fields to the `realm_incoming_webhook_bots` object.

**Feature level 206**

* `POST /calls/zoom/create`: Added `is_video_call` parameter
  controlling whether to request a Zoom meeting that defaults to
  having video enabled.

**Feature level 205**

* [`POST /register`](/api/register-queue): `streams` field in the response
  now includes [web-public streams](/help/public-access-option) as well.
* [`GET /events`](/api/get-events): Events for stream creation and deletion
  are now sent to clients when a user gains or loses access to any streams
  due to a change in their [role](/help/roles-and-permissions).
* [`GET /events`](/api/get-events): The `subscription` events for `op:
  "peer_add"` are now sent to clients when a user gains access to a stream
  due to a change in their role.

**Feature level 204**

* [`POST /register`](/api/register-queue): Added
  `server_typing_started_wait_period_milliseconds`,
  `server_typing_stopped_wait_period_milliseconds`, and
  `server_typing_started_expiry_period_milliseconds` fields
  for clients to use when implementing [typing
  notifications](/api/set-typing-status) protocol.

**Feature level 203**

* [`POST /register`](/api/register-queue): Add
  `realm_date_created` field to realm data.

**Feature level 202**

* [`PATCH /realm/linkifiers`](/api/reorder-linkifiers): Added new endpoint
  to support changing the order in which linkifiers will be processed.

**Feature level 201**

* `POST /zulip-outgoing-webhook`: Renamed the notification trigger
  `private_message` to `direct_message`.

**Feature level 200**

* [`PATCH /streams/{stream_id}`](/api/update-stream): Added
  `is_default_stream` parameter to change whether the stream is a
  default stream for new users in the organization.
* [`POST /users/me/subscriptions`](/api/subscribe): Added
  `is_default_stream` parameter which determines whether any streams
  created by this request will be default streams for new users.

**Feature level 199**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`GET /streams`](/api/get-streams),
  [`GET /streams/{stream_id}`](/api/get-stream-by-id): Stream objects now
  include a `stream_weekly_traffic` field indicating the stream's level of
  traffic.

**Feature level 198**

* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue),
  [`GET /user_groups`](/api/get-user-groups),
  [`POST /user_groups/create`](/api/create-user-group),
  [`PATCH /user_groups/{user_group_id}`](/api/update-user-group):Renamed
  group setting `can_mention_group_id` to `can_mention_group`.

**Feature level 197**

* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream),
  [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams),
  [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events): Renamed
  stream setting `can_remove_subscribers_group_id`
  to `can_remove_subscribers_group`.

**Feature level 196**

* [`POST /realm/playgrounds`](/api/add-code-playground): `url_prefix` is
  replaced by `url_template`, which only accepts [RFC 6570][rfc6570] compliant
  URL templates. The old prefix format is no longer supported.
* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue):
  `url_prefix` is replaced by `url_template` in `realm_playgrounds` events.

**Feature level 195**

* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue):
  The `default_code_block_language` realm setting is now consistently an
  empty string when no default pygments language code is set. Previously,
  the server had a bug that meant it might represent no default for this
  realm setting as either `null` or an empty string. Clients supporting
  older server versions should treat either value (`null` or `""`) as no
  default being set.

**Feature level 194**

* [`GET /messages`](/api/get-messages),
  [`GET /messages/matches_narrow`](/api/check-messages-match-narrow),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow),
  [`POST /register`](/api/register-queue):
  For [search/narrow filters](/api/construct-narrow) with the `id`
  operator, added support for encoding the message ID operand as either
  a string or an integer. Previously, only string encoding was supported.

**Feature level 193**

* [`POST /messages/{message_id}/reactions`](/api/add-reaction),
  [`DELETE /messages/{message_id}/reactions`](/api/remove-reaction):
  Endpoints return specific error responses if an emoji reaction
  already exists when adding a reaction (`"code": "REACTION_ALREADY_EXISTS"`)
  or if an emoji reaction does not exist when deleting a reaction
  (`"code": "REACTION_DOES_NOT_EXIST"`). Previously, these errors
  returned the `"BAD_REQUEST"` code.

**Feature level 192**

* [`GET /events`](/api/get-events): Stream creation events are now
  sent when guest users gain access to a public stream by being
  subscribed. Guest users previously only received these events when
  subscribed to private streams.

**Feature level 191**

* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue),
  [`GET /user_groups`](/api/get-user-groups): Add `can_mention_group_id` to
  user group objects.
* [`POST /user_groups/create`](/api/create-user-group): Added `can_mention_group_id`
  parameter to support setting the user group whose members can mention the new user
  group.
* [`PATCH /user_groups/{user_group_id}`](/api/update-user-group): Added
  `can_mention_group_id` parameter to support changing the user group whose
  members can mention the specified user group.

**Feature level 190**

* [`DELETE /realm/emoji/{emoji_name}`](/api/deactivate-custom-emoji): This endpoint
  now returns an HTTP status code of 404 when an emoji does not exist, instead of 400.

**Feature level 189**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults),
  [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings):
  Added new boolean user settings  `enable_followed_topic_email_notifications`,
  `enable_followed_topic_push_notifications`,
  `enable_followed_topic_wildcard_mentions_notify`,
  `enable_followed_topic_desktop_notifications`
  and `enable_followed_topic_audible_notifications` to control whether a user
  receives email, push, wildcard mention, visual desktop and audible desktop
  notifications, respectively, for messages sent to followed topics.

**Feature level 188**

* [`POST /users/me/muted_users/{muted_user_id}`](/api/mute-user),
  [`DELETE /users/me/muted_users/{muted_user_id}`](/api/unmute-user):
  Added support to mute/unmute bot users.

Feature levels 186-187 are reserved for future use in 7.x maintenance
releases.

## Changes in Zulip 7.0

**Feature level 185**

No changes; feature level used for Zulip 7.0 release.

**Feature level 184**

* [`PATCH /scheduled_messages/<int:scheduled_message_id>`](/api/update-scheduled-message):
  Added new endpoint for editing an existing scheduled message.
* [`POST /scheduled_messages`](/api/create-scheduled-message):
  Removed optional `scheduled_message_id` parameter, which had
  been a previous way for clients to support editing an existing
  scheduled message.

**Feature level 183**

* [`POST /register`](/api/register-queue): Removed the
  `realm_community_topic_editing_limit_seconds` property, which was no
  longer in use. The time limit for editing topics is controlled by the
  realm setting `move_messages_within_stream_limit_seconds`, see feature
  level 162.
* [`GET /events`](/api/get-events): Removed the `community_topic_editing_limit_seconds`
  property from realm `update_dict` event documentation, because it was
  never returned as a changed property in this event and was only ever
  returned in the [`POST /register`](/api/register-queue) response.

**Feature level 182**

* `POST /export/realm`: This endpoint now returns the ID of the data
  export object created by the request.

**Feature level 181**

* [`GET /scheduled_messages`](/api/get-scheduled-messages), [`GET
  /events`](/api/get-events), [`POST /register`](/api/register-queue):
  Added `failed` boolean field to scheduled message objects to
  indicate if the server tried to send the scheduled message and was
  unsuccessful. Clients that support unscheduling and editing
  scheduled messages should use this field to indicate to the user
  when a scheduled message failed to send at the appointed time.

**Feature level 180**

* [`POST /invites`](/api/send-invites): Added support for invitations specifying
  the empty list as the user's initial stream subscriptions. Previously, this
  returned an error. This change was also backported to Zulip 6.2, and
  is available at feature levels 157-158 as well.

**Feature level 179**

* [`POST /scheduled_messages`](/api/create-scheduled-message):
  Added new endpoint to create and edit scheduled messages.
* [`GET /events`](/api/get-events):
  Added `scheduled_messages` events sent to clients when a user creates,
  edits or deletes scheduled messages.
* [`POST /register`](/api/register-queue):
  Added an optional `scheduled_messages` field to that includes all
  of the undelivered scheduled messages for the current user.

**Feature level 178**

* `POST /users/me/presence`,
  [`GET /users/<user_id_or_email>/presence`](/api/get-user-presence),
  [`GET /realm/presence`](/api/get-presence),
  [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events):
  The server no longer stores which client submitted presence data,
  and presence responses from the server will always contain the
  `"aggregated"` and `"website"` keys.

**Feature level 177**

* [`GET /messages`](/api/get-messages),
  [`GET /messages/matches_narrow`](/api/check-messages-match-narrow),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow),
  [`POST /register`](/api/register-queue):
  Added support for three [search/narrow filters](/api/construct-narrow)
  related to direct messages: `is:dm`, `dm` and `dm-including`.
  The `dm` operator replaces and deprecates the `pm-with` operator.
  The `is:dm` filter replaces and deprecates the `is:private` filter.
  The `dm-including` operator replaces and deprecates the `group-pm-with`
  operator. Because existing Zulip messages may have links with these
  legacy filters, they are still supported for backwards-compatibility.

**Feature level 176**

* [`POST /realm/filters`](/api/add-linkifier),
  [`PATCH /realm/filters/<int:filter_id>`](/api/update-linkifier):
  The `url_format_string` parameter is replaced by `url_template`.
  [Linkifiers](/help/add-a-custom-linkifier) now only accept
  [RFC 6570][rfc6570] compliant URL templates. The old URL format
  strings are no longer supported.
* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue):
  The `url_format_string` key in `realm_linkifiers` objects is replaced
  by `url_template`. For backwards-compatibility, clients that do not
  support the `linkifier_url_template`
  [client capability](/api/register-queue#parameter-client_capabilities)
  will receive an empty `realm_linkifiers` array in the `/register`
  response and not receive `realm_linkifiers` events. Unconditionally,
  the deprecated `realm_filters` event type returns an empty array in
  the `/register` response and these events are no longer sent to
  clients.

**Feature level 175**

* [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings),
  [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added new user setting `web_mark_read_on_scroll_policy`. Clients may use this to
  determine the user's preference on whether to mark messages as read or not when
  scrolling through their message feed.

**Feature level 174**:

* [`POST /typing`](/api/set-typing-status), [`POST /messages`](/api/send-message):
  Added `"direct"` as the preferred way to indicate a direct message for the
  `type` parameter, deprecating the original `"private"`. While `"private"`
  is still supported for direct messages, clients are encouraged to use
  the modern convention with servers that support it, because support for
  `"private"` may eventually be removed.

**Feature level 173**:

* [`GET /scheduled_messages`](/api/get-scheduled-messages), [`DELETE
  /scheduled_messages/<int:scheduled_message_id>`](/api/delete-scheduled-message):
  Added new endpoints to fetch and delete scheduled messages.

**Feature level 172**

* [`PATCH /messages/{message_id}`](/api/update-message):
  [Topic editing restrictions](/help/restrict-moving-messages) now apply
  to stream messages without a topic.
* [`PATCH /messages/{message_id}`](/api/update-message): When users, other
  than organization administrators and moderators, use
  `"propagate_mode": "change_all"` to move messages that have passed the
  organization's time limit for updating a message's topic and/or stream,
  this endpoint now returns an error response
  (`"code": "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED"`).

**Feature level 171**:

* [`POST /fetch_api_key`](/api/fetch-api-key),
  [`POST /dev_fetch_api_key`](/api/dev-fetch-api-key): The return values
  for these endpoints now include the unique ID of the user who owns the
  API key.

**Feature level 170**

* [`POST /user_topics`](/api/update-user-topic): Added a new endpoint to
  update a user's personal preferences for a topic, which deprecates the
  [`PATCH /users/me/subscriptions/muted_topics`](/api/mute-topic) endpoint.
  The deprecated endpoint is maintained for backwards-compatibility but may be
  removed in a future release.
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events):
  Unmuted added as a visibility policy option to the objects sent in response
  to the `user_topic` event.

**Feature level 169**

* [`PATCH /users/me/subscriptions/muted_topics`](/api/mute-topic):
  Trying to mute a topic that is already muted or unmute a topic
  that was not previously muted now results in a success response
  rather than an error.

**Feature level 168**

* [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings),
  [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Replaced the boolean user setting `realm_name_in_notifications`
  with an integer `realm_name_in_email_notifications_policy`.

**Feature level 167**

* [All REST API endpoints](/api/rest-error-handling#ignored-parameters):
  Implemented `ignored_parameters_unsupported` as a possible return value
  in the JSON success response for all endpoints. This value is a array
  of any parameters that were sent in the request by the client that are
  not supported by the endpoint. Previously, unsupported parameters were
  silently ignored, except in the subset of endpoints which already
  supported this return value; see feature levels 111, 96 and 78.

**Feature level 166**

* [`POST /messages`](/api/send-message): Eliminated the undocumented
  `realm_str` parameter. This parameter was already redundant due to
  it needing to match the realm of the user making the request, otherwise
  returning an authorization error. With this, the parameter is removed,
  meaning that if provided in the API request, it will be ignored.

**Feature level 165**

* [`PATCH /user_groups/{user_group_id}`](/api/update-user-group): The
  `name` and `description` parameters are now optional.

**Feature level 164**

* [`POST /register`](/api/register-queue): Added the
  `server_presence_ping_interval_seconds` and
  `server_presence_offline_threshold_seconds` fields for clients
  to use when implementing the [presence](/api/get-presence) system.

**Feature level 163**

* [`GET /users`](/api/get-users), [`GET /users/{user_id}`](/api/get-user),
  [`GET /users/{email}`](/api/get-user-by-email),
  [`GET /users/me`](/api/get-own-user), [`GET /events`](/api/get-events):
  The `delivery_email` field is always present in user objects, including
  the case when a user's `email_address_visibility` is set to everyone.
  The value will be `null` if the requester does not have access to the
  user's real email. For bot users, the `delivery_email` field is always
  set to the bot user's real email.
* [`GET /events`](/api/get-events): Event for updating a user's
  `delivery_email` is now sent to all users who have access to it, and
  is also sent when a user's `email_address_visibility` setting changes.
* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue)
  [`GET /users`](/api/get-users), [`GET /users/{user_id}`](/api/get-user),
  [`GET /users/{email}`](/api/get-user-by-email),
  [`GET /users/me`](/api/get-own-user), [`GET /messages`](/api/get-messages),
  [`GET /messages/{message_id}`](/api/get-message): Whether the `avatar_url`
  field in message and user objects returned by these endpoints can be `null`
  now depends on if the current user has access to the other user's real
  email address based on the other user's `email_address_visibility` policy.
* [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings),
  [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added user setting `email_address_visibility`, to replace the
  realm setting `email_address_visibility`.
* [`POST /register`](/api/register-queue), `PATCH /realm`: Removed realm
  setting `email_address_visibility`.

**Feature level 162**

* `PATCH /realm`, [`POST /register`](/api/register-queue),
   [`GET /events`](/api/get-events): Added two new realm settings
  `move_messages_within_stream_limit_seconds` and
  `move_messages_between_streams_limit_seconds` for organizations to
  configure time limits for editing topics and moving messages between streams.
* [`PATCH /messages/{message_id}`](/api/update-message): For users other than
  administrators and moderators, the time limit for editing topics is now
  controlled via the realm setting `move_messages_within_stream_limit_seconds`
  and the time limit for moving messages between streams is now controlled by
  the realm setting `move_messages_between_streams_limit_seconds`.

**Feature level 161**

* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added
  `can_remove_subscribers_group_id` parameter to support setting and
  changing the user group whose members can remove other subscribers
  from the specified stream.
* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Expanded the
  situations where users can use this endpoint to unsubscribe other
  users from a stream to include the case where the current user has
  access to the stream and is a member of the user group specified by
  the `can_remove_subscribers_group_id` for the stream.

**Feature level 160**

* `POST /api/v1/jwt/fetch_api_key`: Added new endpoint to fetch API
  keys using JSON Web Token (JWT) authentication.
* `accounts/login/jwt/`: Adjusted format of requests to undocumented,
  optional endpoint for JWT authentication log in support.

**Feature level 159**

* `PATCH /realm`, [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events):
  Nobody added as an option for the realm settings `edit_topic_policy`
  and `move_messages_between_streams_policy`.
* [`PATCH /messages/{message_id}`](/api/update-message): Permission
  to edit the stream and/or topic of messages no longer depends on the
  realm setting `allow_message_editing`.
* [`PATCH /messages/{message_id}`](/api/update-message): The user who
  sent the message can no longer edit the message's topic indefinitely.

Feature level 158 is reserved for future use in 6.x maintenance
releases.

## Changes in Zulip 6.2

**Feature level 157**

* [`POST /invites`](/api/send-invites): Added support for invitations specifying
  the empty list as the user's initial stream subscriptions. Previously, this
  returned an error. This change was backported from the Zulip 7.0
  branch, and thus is available at feature levels 157-158 and 180+.

## Changes in Zulip 6.0

**Feature level 156**

No changes; feature level used for Zulip 6.0 release.

**Feature level 155**

* [`GET /messages`](/api/get-messages): The new `include_anchor`
  parameter controls whether a message with ID matching the specified
  `anchor` should be included.
* The `update_message_flags` event sent by [`POST
  /messages/flags`](/api/update-message-flags) no longer redundantly
  lists messages where the flag was set to the same state it was
  already in.
* [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow):
  This new endpoint allows updating message flags on a range of
  messages within a narrow.

**Feature level 154**

* [`POST /streams/{stream_id}/delete_topic`](/api/delete-topic):
  When the process of deleting messages times out, but successfully
  deletes some messages in the topic (see feature level 147 for when
  this endpoint started deleting messages in batches), a success
  response with `"result": "partially_completed"` will now be returned
  by the server, analogically to the `POST /mark_all_as_read` endpoint
  (see feature level 153 entry below).

**Feature level 153**

* [`POST /mark_all_as_read`](/api/mark-all-as-read): Messages are now
  marked as read in batches, so that progress will be made even if the
  request times out because of an extremely large number of unread
  messages to process. Upon timeout, a success response with
  `"result": "partially_completed"` will be returned by the server.

**Feature level 152**

* [`PATCH /messages/{message_id}`](/api/update-message):
  The default value for `send_notification_to_old_thread` was changed from
  `true` to `false`.
  When moving a topic within a stream, the `send_notification_to_old_thread`
  and `send_notification_to_new_thread` parameters are now respected, and by
  default a notification is sent to the new thread.

**Feature level 151**

* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`POST /realm/profile_fields`](/api/create-custom-profile-field),
  [`GET /realm/profile_fields`](/api/get-custom-profile-fields): Added
  pronouns custom profile field type.

**Feature level 150**

* [`GET /events`](/api/get-events): Separate events are now sent on changing
  `allow_message_editing`, `message_content_edit_limit_seconds` and
  `edit_topic_policy` settings, whereas previously one event was sent including
  all of these setting values irrespective of which of them were actually changed.
* `PATCH /realm`: Only changed settings are included in the response data now
  when changing `allow_message_editing`, `edit_topic_policy` and
  `message_content_edit_limit_seconds` settings, instead of including all the
  fields even if one of these settings was changed.

**Feature level 149**

* [`POST /register`](/api/register-queue): The `client_gravatar` and
  `include_subscribers` parameters now return an error for
  [unauthenticated requests](/help/public-access-option) if an
  unsupported value is requested by the client.

**Feature level 148**

* [`POST /users/me/status`](/api/update-status),
  [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events):
  The user status `away` field/parameter is deprecated, and as of this
  feature level are a legacy way to access the user's `presence_enabled`
  setting, with `away = !presence_enabled`. To be removed in a future
  release.

**Feature level 147**

* [`POST /streams/{stream_id}/delete_topic`](/api/delete-topic):
  Messages now are deleted in batches, starting from the newest, so
  that progress will be made even if the request times out because of
  an extremely large topic.

**Feature level 146**

* [`POST /realm/profile_fields`](/api/create-custom-profile-field),
[`GET /realm/profile_fields`](/api/get-custom-profile-fields): Added a
new parameter `display_in_profile_summary`, which clients use to
decide whether to display the field in a small/summary section of the
user's profile.

**Feature level 145**

* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Normal users can
  now remove bots that they own from streams.

**Feature level 144**

* [`GET /messages/{message_id}/read_receipts`](/api/get-read-receipts):
  The `user_ids` array returned by the server no longer includes IDs
  of users who have been muted by or have muted the current user.

**Feature level 143**

* `PATCH /realm`: The `disallow_disposable_email_addresses`,
  `emails_restricted_to_domains`, `invite_required`, and
  `waiting_period_threshold` settings can no longer be changed by
  organization administrators who are not owners.
* `PATCH /realm/domains`, `POST /realm/domains`, `DELETE
  /realm/domains`: Organization administrators who are not owners can
  no longer access these endpoints.

**Feature level 142**

* [`GET /users/me/subscriptions`](/api/get-subscriptions), [`GET
  /streams`](/api/get-streams), [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events): Added `can_remove_subscribers_group_id`
  field to Stream and Subscription objects.

**Feature level 141**

* [`POST /register`](/api/register-queue), [`PATCH
  /settings`](/api/update-settings), [`PATCH
  /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added new `user_list_style` display setting, which controls the
  layout of the right sidebar.

**Feature level 140**

* [`POST /register`](/api/register-queue): Added string field `server_emoji_data_url`
  to the response.

**Feature level 139**

* [`GET /get-events`](/api/get-events): When a user mutes or unmutes
  their subscription to a stream, a `subscription` update event
  is now sent for the `is_muted` property and for the deprecated
  `in_home_view` property to support clients fully migrating to use the
  `is_muted` property. Prior to this feature level, only one event was
  sent to clients with the deprecated `in_home_view` property.

**Feature level 138**

* [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events): `message_content_edit_limit_seconds`
  now represents no limit using `null`, instead of the integer 0.
* `PATCH /realm`: One now sets `message_content_edit_limit_seconds`
  to no limit by passing the string `unlimited`, rather than the
  integer 0.

**Feature level 137**

* [`GET /messages/{message_id}/read_receipts`](/api/get-read-receipts):
  Added new endpoint to fetch read receipts for a message.
* [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events), `PATCH /realm`: Added new
  `enable_read_receipts` realm setting.

**Feature level 136**

* [`PATCH /streams/{stream_id}`](/api/update-stream): The endpoint
  now returns an error for a request to make a public stream with
  protected history which was previously ignored silently.
* [`PATCH /streams/{stream_id}`](/api/update-stream): Added support
  to change access to history of the stream by only passing
  `history_public_to_subscribers` parameter without `is_private`
  and `is_web_public` parameters.

**Feature level 135**

* [`DELETE /user/{user_id}`](/api/deactivate-user): Added
  `deactivation_notification_comment` field controlling whether the
  user receives a notification email about their deactivation.

**Feature level 134**

* [`GET /events`](/api/get-events): Added `user_topic` event type
  which is sent when a topic is muted or unmuted. This generalizes and
  replaces the previous `muted_topics` array, which will no longer be
  sent if `user_topic` was included in `event_types` when registering
  the queue.
* [`POST /register`](/api/register-queue): Added `user_topics` array
  to the response. This generalizes and replaces the previous
  `muted_topics` array, which will no longer be sent if `user_topic`
  is included in `fetch_event_types`.
* [`GET /events`](/api/get-events): When private streams are made
  public, `stream` events for `op: "create"` and `subscription` events
  for `op: "peer_add"` are now sent to clients.

**Feature level 133**

* [`POST /register`](/api/register-queue), `PATCH /realm`: Removed
  stream administrators option from `wildcard_mention_policy` setting.
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`GET /users/me/subscriptions`](/api/get-subscriptions): Removed
  `role` field from subscription objects.

**Feature level 132**

* [`GET /streams/{stream_id}`](/api/get-stream-by-id):
  Added new endpoint to get a stream by ID.

**Feature level 131**

* [`GET /user_groups`](/api/get-user-groups),[`POST
  /register`](/api/register-queue): Renamed `subgroups` field in
  the user group objects to `direct_subgroup_ids`.
* [`GET /events`](/api/get-events): Renamed `subgroup_ids` field
  in the group object to `direct_subgroup_ids`.

**Feature level 130**

* `PATCH /bots/{bot_user_id}`: Added support for changing a bot's role
  via this endpoint. Previously, this could only be done via [`PATCH
  /users/{user_id}`](/api/update-user).

**Feature level 129**

* [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events), `PATCH /realm`: Added realm setting
  `want_advertise_in_communities_directory` for organizations to give
  permission to be advertised in the Zulip communities directory.

**Feature level 128**

* [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events), `PATCH /realm`: Added
  `org_type` realm setting.

**Feature level 127**

* [`GET /user_groups`](/api/get-user-groups),[`POST
  /register`](/api/register-queue): Added `subgroups` field,
  which is a list of IDs of all the subgroups of the user group, to
  user group objects.
* [`GET /events`](/api/get-events): Added new `user_group` events
  operations for live updates to subgroups (`add_subgroups` and
  `remove_subgroups`).
* [`PATCH /user_groups/{user_group_id}/subgroups`](/api/update-user-group-subgroups):
  Added new endpoint for updating subgroups of a user group.
* [`GET /user_groups/{user_group_id}/members/{user_id}`](/api/get-is-user-group-member):
  Added new endpoint for checking whether a given user is member of a
  given user group.
* [`GET /user_groups/{user_group_id}/members`](/api/get-user-group-members):
  Added new endpoint to get members of a user group.
* [`GET /user_groups/{user_group_id}/members`](/api/get-user-group-subgroups):
  Added new endpoint to get subgroups of a user group.

**Feature level 126**

* [`POST /invites`](/api/send-invites),
  [`POST /invites/multiuse`](/api/create-invite-link): Replaced
  `invite_expires_in_days` parameter with `invite_expires_in_minutes`.

**Feature level 125**

* [`POST /register`](/api/register-queue), [`PATCH
  /settings`](/api/update-settings), [`PATCH
  /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added new `display_emoji_reaction_users` display setting,
  controlling whether to display the names of users with emoji reactions.

Feature levels 123-124 are reserved for future use in 5.x maintenance
releases.

## Changes in Zulip 5.0

**Feature level 122**

No changes; feature level used for Zulip 5.0 release.

**Feature level 121**

* [`GET /events`](/api/get-events): Added `message_details` field
  appearing in message flag update events when marking previously read
  messages as unread.

**Feature level 120**

* [`GET /messages/{message_id}`](/api/get-message): This endpoint
  now sends the full message details. Previously, it only returned
  the message's raw Markdown content.

**Feature level 119**

* [`POST /register`](/api/register-queue): Added `other_user_id` field
  to the `pms` objects in the `unread_msgs` data set, deprecating the
  less clearly named `sender_id` field. This change was motivated by
  the possibility that a one-on-one direct message sent by the current
  user to another user could be marked as unread. The `sender_id` field
  is still present for backwards compatibility with older server versions.

**Feature level 118**

* [`GET /messages`](/api/get-messages), [`GET
  /events`](/api/get-events): Improved the format of the
  `edit_history` object within message objects. Entries for stream
  edits now include a both a `prev_stream` and `stream` field to
  indicate the previous and current stream IDs. Prior to this feature
  level, only the `prev_stream` field was present. Entries for topic
  edits now include both a `prev_topic` and `topic` field to indicate
  the previous and current topic, replacing the `prev_subject`
  field. These changes substantially simplify client complexity for
  processing historical message edits.

* [`GET /messages/{message_id}/history`](/api/get-message-history):
  Added `stream` field to message history `snapshot` indicating
  the updated stream ID of messages moved to a new stream.

**Feature level 117**

* [`POST /invites`](/api/send-invites),
  [`POST /invites/multiuse`](/api/create-invite-link): Added support
  for passing `null` as the `invite_expires_in_days` parameter to
  request an invitation that never expires.

**Feature level 116**

* [`GET /server_settings`](/api/get-server-settings): Added
  `realm_web_public_access_enabled` as a realm-specific server setting,
  which can be used by clients to detect whether the realm allows and
  has at least one [web-public stream](/help/public-access-option).

**Feature level 115**

* Mobile push notifications about stream messages now include the
  `stream_id` field.

**Feature level 114**

* [`GET /events`](/api/get-events): Added `rendering_only` field to
  `update_message` event type to indicate if the message change only
  updated the rendering of the message or if it was the result of a
  user interaction.

* [`GET /events`](/api/get-events): Updated `update_message` event type
  to always include `edit_timestamp` and `user_id` fields. If the event
  only updates the rendering of the message, then the `user_id` field
  will be present, but with a value of null as the update was not the
  result of a user interaction.

**Feature level 113**

* `GET /realm/emoji`, `POST /realm/emoji/{emoji_name}`, [`GET
  /events`](/api/get-events), [`POST /register`](/api/register-queue):
  The `still_url` field for custom emoji objects is now always
  present, with a value of null for non-animated emoji. Previously, it
  only was present for animated emoji.

**Feature level 112**

* [`GET /events`](/api/get-events): Updated `update_message` event type
  to include `stream_id` field for all edits to stream messages.

**Feature level 111**

* [`POST /users/me/subscriptions/properties`](/api/update-subscription-settings):
  Removed `subscription_data` from response object, replacing it with
  `ignored_parameters_unsupported`.

**Feature level 110**

* [`POST /register`](/api/register-queue): Added
  `server_web_public_streams_enabled` to the response.

**Feature level 109**

* [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events), `PATCH /realm`: Added new
  `enable_spectator_access` realm setting.

**Feature level 108**

* In the mobile application authentication flow, the authenticated
  user's `user_id` is now included in the parameters encoded in the
  final `zulip://` redirect URL.

**Feature level 107**

* [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings),
  [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added user setting `escape_navigates_to_default_view` to allow users to
  [disable the keyboard shortcut](/help/configure-home-view) for the `Esc` key that
  navigates the app to the default view.

**Feature level 106**

* [`PATCH /user/{user_id}`](/api/update-user): Removed unnecessary JSON-encoding of string
  parameter `full_name`.

**Feature level 105**

* [`POST /register`](/api/register-queue), [`PATCH
  /settings`](/api/update-settings), [`PATCH
  /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added three new privacy settings: `send_private_typing_notifications`,
  `send_stream_typing_notifications`, and `send_read_receipts`.

**Feature level 104**

* `PATCH /realm`: Added `string_id` parameter for changing an
  organization's subdomain. Currently, this is only allowed for
  changing a demo organization to a normal one.

**Feature level 103**

* [`POST /register`](/api/register-queue): Added `create_web_public_stream_policy`
  policy for which users can create web-public streams.
* [`GET /events`](/api/get-events), `PATCH /realm`: Added support for updating
  `create_web_public_stream_policy`.
* [`POST /register`](/api/register-queue): Added `can_create_web_public_streams` boolean
  field to the response.

**Feature level 102**

* [`POST /register`](/api/register-queue), `PATCH /realm`: The
  `create_stream_policy` setting was split into two settings for
  different types of streams: `create_private_stream_policy` and
  `create_public_stream_policy`.
* [`POST /register`](/api/register-queue): The `create_stream_policy`
  property was deprecated in favor of the
  `create_private_stream_policy` and `create_public_stream_policy`
  properties, but it still available for backwards-compatibility.

**Feature level 101**

* [`POST /register`](/api/register-queue), `PATCH /realm`: Replaced
  the `allow_message_deleting` boolean field with an integer field
  `delete_own_message_policy` defining which roles can delete messages
  they had sent.

**Feature level 100**

* [`POST /register`](/api/register-queue), [`GET
  /events`](/api/get-events): `message_content_delete_limit_seconds`
  now represents no limit using `null`, instead of the integer 0, and 0 is
  no longer a possible value with any meaning.
* `PATCH /realm`: One now sets `message_content_delete_limit_seconds`
  to no limit by passing the string `unlimited`, rather than the
  integer 0.

**Feature level 99**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults),
  `PATCH /realm`: The `default_twenty_four_hour_time` parameter to
  `PATCH /realm` has been replaced by the `twenty_four_hour_time` parameter
  to `PATCH /realm/user_settings_defaults`, to match the new model for
  user preference defaults settings.

* [`POST /register`](/api/register-queue): Removed `realm_default_twenty_four_hour_time`
  from the response object. This value is now available in the
  `twenty_four_hour_time` field of the `realm_user_settings_default` object.

**Feature level 98**

* [`POST /users/me/subscriptions`](/api/subscribe): Added `is_web_public` parameter
  for requesting the creation of a web-public stream.
* [`PATCH /streams/{stream_id}`](/api/update-stream): Added
  `is_web_public` parameter for converting a stream into a web-public stream.

**Feature level 97**

* `GET /realm/emoji`, `POST /realm/emoji/{emoji_name}`, [`GET
  /events`](/api/get-events), [`POST /register`](/api/register-queue):
  Custom emoji objects may now contain a `still_url` field, with the
  URL of a PNG still image version of the emoji. This field will only be
  present for animated emoji.

**Feature level 96**

* [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added new endpoint to update default values of user settings in a realm.
* [`POST /invites`](/api/send-invites),
  [`POST /invites/multiuse`](/api/create-invite-link): Added
  `invite_expires_in_days` parameter encoding the number days before
  the invitation should expire.

**Feature level 95**

* [`POST /register`](/api/register-queue): Added
  `realm_user_settings_defaults` object, containing default values of
  personal user settings for new users in the realm.

* [`GET /events`](/api/get-events): Added
  `realm_user_settings_defaults` event type, which is sent when the
  organization's configured default settings for new users change.

**Feature level 94**

* [`POST /register`](/api/register-queue): Added
  `demo_organization_scheduled_deletion_date` field to realm data.

**Feature level 93**

* [`POST /register`](/api/register-queue), [`GET /user_groups`](/api/get-user-groups),
  [`GET /events`](/api/get-events): Added `is_system_group` field to user group
  objects.

**Feature level 92**

* [`GET /messages`](/api/get-messages), [`POST
  /register`](/api/register-queue), [`GET /users`](/api/get-users),
  [`GET /users/{user_id}`](/api/get-user), [`GET
  /users/{email}`](/api/get-user-by-email): The `client_gravatar`
  parameter now defaults to `true`.

**Feature level 91**

* `PATCH /realm`, [`PATCH /streams/{stream_id}`](/api/update-stream):
  These endpoints now accept `"unlimited"` for `message_retention_days`,
  replacing `"forever"` as the way to encode a retention policy where
  messages are not automatically deleted.

**Feature level 90**

* [`POST /register`](/api/register-queue): The `unread_msgs` section
  of the response no longer includes `sender_ids` in the `streams`
  dictionaries. These were removed because no clients were interested
  in using the data, which required substantial complexity to
  construct correctly.

**Feature level 89**

* [`GET /events`](/api/get-events): Introduced the `user_settings`
  event type, unifying and replacing the previous
  `update_display_settings` and `update_global_notifications` event
  types. The legacy event types are still supported for backwards
  compatibility, but will be removed in a future release.
* [`POST /register`](/api/register-queue): Added `user_settings` field
  in the response, which is a dictionary containing all the user's
  personal settings. For backwards-compatibility, individual settings
  will still appear in the top-level response for clients don't
  support the `user_settings_object` client capability.
* [`POST /register`](/api/register-queue): Added the
  `user_settings_object` property to supported `client_capabilities`.
  When enabled, the server will not include a duplicate copy of
  personal settings in the top-level response.
* [`GET /events`](/api/get-events): `update_display_settings` and
  `update_global_notifications` events now only sent to clients that
  did not include `user_settings_object` in their
  `client_capabilities` when the event queue was created.

**Feature level 88**

* [`POST /register`](/api/register-queue): Added `zulip_merge_base`
  field to the response.
* [`GET /events`](/api/get-events): Added new `zulip_merge_base`
  field to the `restart` event.
* [`GET /server_settings`](/api/get-server-settings): Added
  `zulip_merge_base` to the responses which can be used to
  make "About Zulip" widgets in clients.

**Feature level 87**

* [`PATCH /settings`](/api/update-settings): Added a new
  `enable_drafts_synchronization` setting, which controls whether the
  syncing drafts between different clients is enabled.

* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue):
  Added new `enable_drafts_synchronization` setting under
  `update_display_settings`.

* [`GET /drafts`](/api/get-drafts): Added new endpoint to fetch user's
  synced drafts from the server.

* [`POST /drafts`](/api/create-drafts): Added new endpoint to create
  drafts when syncing has been enabled.

* [`PATCH /drafts/{draft_id}`](/api/edit-draft): Added new endpoint
  to edit a draft already owned by the user.

* [`DELETE /drafts/{draft_id}`](/api/delete-draft): Added new endpoint
  to delete a draft already owned by the user.

**Feature level 86**

* [`GET /events`](/api/get-events): Added `emoji_name`,
  `emoji_code`, and `reaction_type` fields to `user_status` objects.
* [`POST /register`](/api/register-queue): Added `emoji_name`,
  `emoji_code`, and `reaction_type` fields to `user_status` objects.
* [`POST /users/me/status`](/api/update-status): Added support for new
  `emoji_name`, `emoji_code`, and `reaction_type` parameters.

**Feature level 85**

* [`POST /register`](/api/register-queue), `PATCH /realm`: Replaced `add_emoji_by_admins_only`
  field with an integer field `add_custom_emoji_policy`.

**Feature level 84**

* [`POST /register`](/api/register-queue): The `enter_sends` setting
  is now sent when `update_display_setting` is present in
  `fetch_event_types` instead of `realm_user`.

**Feature level 83**

* [`POST /register`](/api/register-queue): The `cross_realm_bots`
  section of the response now uses the `is_system_bot` flag to
  indicate whether the bot is a system bot.

**Feature level 82**

* [`PATCH /settings`](/api/update-settings) now accepts a new
  `email_notifications_batching_period_seconds` field for setting the
  time duration for which the server will collect email notifications
  before sending them.

**Feature level 81**

* `POST /users/me/enter-sends` has been removed. The `enter_sends`
  setting is now edited using the normal [`PATCH
  /settings`](/api/update-settings) endpoint.

**Feature level 80**

* [`PATCH /settings`](/api/update-settings): The
  `/settings/notifications` and `/settings/display` endpoints were
  merged into the main `/settings` endpoint; now all personal settings
  should be edited using that single endpoint. The old URLs are
  preserved as deprecated aliases for backwards compatibility.

**Feature level 79**

* [`GET /users/me/subscriptions`](/api/get-subscriptions): The
  `subscribers` field now returns user IDs if `include_subscribers` is
  passed. Previously, this endpoint returned user display email
  addresses in this field.
* `GET /streams/{stream_id}/members`: This endpoint now returns user
  IDs. Previously, it returned display email addresses.

**Feature level 78**

* [`PATCH /settings`](/api/update-settings): Added
  `ignored_parameters_unsupported` field, which is a list of
  parameters that were ignored by the endpoint, to the response
  object.

* [`PATCH /settings`](/api/update-settings): Removed `full_name` and
  `account_email` fields from the response object.

**Feature level 77**

* [`GET /events`](/api/get-events): Removed `recipient_id` and
  `sender_id` field in responses of `delete_message` event when
  `message_type` is `private`.

**Feature level 76**

* [`POST /fetch_api_key`](/api/fetch-api-key), [`POST
  /dev_fetch_api_key`](/api/dev-fetch-api-key): The HTTP status for
  authentication errors is now 401. This was previously 403.
* All API endpoints now use the HTTP 401 error status for API requests
  involving a deactivated user or realm. This was previously 403.
* Mobile push notifications now include the `mentioned_user_group_id`
  and `mentioned_user_group_name` fields when a user group containing
  the user is mentioned.  Previously, these were indistinguishable
  from personal mentions (as both types have `trigger="mention"`).

**Feature level 75**

* [`POST /register`](/api/register-queue), `PATCH /realm`: Replaced `allow_community_topic_editing`
  field with an integer field `edit_topic_policy`.

**Feature level 74**

* [`POST /register`](/api/register-queue): Added `server_needs_upgrade`
  and `event_queue_longpoll_timeout_seconds` field when fetching
  realm data.

**Feature level 73**

* [`GET /users`](/api/get-users), [`GET /users/{user_id}`](/api/get-user),
  [`GET /users/{email}`](/api/get-user-by-email) and
  [`GET /users/me`](/api/get-own-user): Added is `user_billing_admin` field to
  returned user objects.
* [`GET /events`](/api/get-events): Added `is_billing_admin` field to
  user objects sent in `realm_user` events.
* [`POST /register`](/api/register-queue): Added `is_billing_admin` field
  in the user objects returned in the `realm_users` field.

**Feature level 72**

* [`POST /register`](/api/register-queue): Renamed `max_icon_file_size` to
  `max_icon_file_size_mib`, `realm_upload_quota` to `realm_upload_quota_mib`
  and `max_logo_file_size` to `max_logo_file_size_mib`.

**Feature level 71**

* [`GET /events`](/api/get-events): Added `is_web_public` field to
  `stream` events changing `invite_only`.

**Feature level 70**

* [`POST /register`](/api/register-queue): Added new top-level
  `server_timestamp` field when fetching presence data, to match the
  existing presence API.

Feature levels 66-69 are reserved for future use in 4.x maintenance
releases.

## Changes in Zulip 4.0

**Feature level 65**

No changes; feature level used for Zulip 4.0 release.

**Feature level 64**

* `PATCH /streams/{stream_id}`: Removed unnecessary JSON-encoding of string
  parameters `new_name` and `description`.
* `PATCH /settings/display`: Removed unnecessary JSON-encoding of string
  parameters `default_view`, `emojiset` and `timezone`.

**Feature level 63**

* `PATCH /settings/notifications`: Removed unnecessary JSON-encoding of string
  parameter `notification_sound`.
* `PATCH /settings/display`: Removed unnecessary JSON-encoding of string
  parameter `default_language`.
* `POST /users/me/tutorial_status`: Removed unnecessary JSON-encoding of string
  parameter `status`.
* `POST /realm/domains`: Removed unnecessary JSON-encoding of string
  parameter `domain`.
* `PATCH /default_stream_groups/{user_id}`: Removed unnecessary JSON-encoding of string
  parameters `new_group_name` and `new_description`.
* `POST /users/me/hotspots`: Removed unnecessary JSON-encoding of string
  parameter `hotspot`.

**Feature level 62**

* Added `moderators only` option for `wildcard_mention_policy`.

**Feature level 61**

* [`POST /invites`](/api/send-invites),
  [`POST /invites/multiuse`](/api/create-invite-link): Added support
  for inviting users as moderators.

**Feature level 60**

* [`POST /register`](/api/register-queue): Added a new boolean field
  `is_moderator`, similar to the existing `is_admin`, `is_owner` and
  `is_guest` fields, to the response.
* [`PATCH /users/{user_id}`](/api/update-user): Added support for
  changing a user's organization-level role to moderator.
* API endpoints that return `role` values can now return `300`, the
  encoding of the moderator role.

**Feature level 59**

* [`GET /users`](/api/get-users), [`GET /users/{user_id}`](/api/get-user),
  [`GET /users/{email}`](/api/get-user-by-email) and
  [`GET /users/me`](/api/get-own-user): Added `role` field to returned
  user objects.
* [`GET /events`](/api/get-events): Added `role` field to
  user objects sent in `realm_user` events.
* [`POST /register`](/api/register-queue): Added `role` field
  in the user objects returned in the `realm_users` field.
* [`GET /events`](/api/get-events): Added new `zulip_version` and
  `zulip_feature_level` fields to the `restart` event.

**Feature level 58**

* [`POST /register`](/api/register-queue): Added the new
  `stream_typing_notifications` property to supported
  `client_capabilities`.
* [`GET /events`](/api/get-events): Extended format for `typing`
  events to support typing notifications in stream messages. These new
  events are only sent to clients with `client_capabilities`
  showing support for `stream_typing_notifications`.
* [`POST /typing`](/api/set-typing-status): Added support
  for sending typing notifications for stream messages.

**Feature level 57**

* [`PATCH /realm/filters/{filter_id}`](/api/update-linkifier): New
  endpoint added to update a realm linkifier.

**Feature level 56**

* [`POST /register`](/api/register-queue): Added a new setting
  `move_messages_between_streams_policy` for controlling who can
  move messages between streams.

**Feature level 55**

* [`POST /register`](/api/register-queue): Added `realm_giphy_rating`
  and `giphy_rating_options` fields.
* `PATCH /realm`: Added `giphy_rating` parameter.

**Feature level 54**

* `GET /realm/filters` has been removed and replace with [`GET
  /realm/linkifiers`](/api/get-linkifiers) which returns the data in a
  cleaner dictionary format.
* [`GET /events`](/api/get-events): Introduced new event type
  `realm_linkifiers`.  The previous `realm_filters` event type is
  still supported for backwards compatibility, but will be removed in
  a future release.
* [`POST /register`](/api/register-queue): The response now supports a
  `realm_linkifiers` event type, containing the same data as the
  legacy `realm_filters` key, with a more extensible object
  format. The previous `realm_filters` event type is still supported
  for backwards compatibility, but will be removed in a future
  release. The legacy `realm_filters` key is deprecated but remains
  available for backwards compatibility.

**Feature level 53**

* [`POST /register`](/api/register-queue): Added `max_topic_length`
  and `max_message_length`, and renamed `max_stream_name_length` and
  `max_stream_description_length` to allow clients to transparently
  support these values changing in a future server version.

**Feature level 52**

* `PATCH /realm`: Removed unnecessary JSON-encoding of string
  parameters `name`, `description`, `default_language`, and
  `default_code_block_language`.

**Feature level 51**

* [`POST /register`](/api/register-queue): Added a new boolean field
`can_invite_others_to_realm`.

**Feature level 50**

* [`POST /register`](/api/register-queue): Replaced `invite_by_admins_only`
field with an integer field `invite_to_realm_policy`.

**Feature level 49**

* Added new [`POST /realm/playground`](/api/add-code-playground) and
  [`DELETE /realm/playground/{playground_id}`](/api/remove-code-playground)
  endpoints for code playgrounds.
* [`GET /events`](/api/get-events): A new `realm_playgrounds` events
  is sent when changes are made to a set of configured code playgrounds for
  an organization.
* [`POST /register`](/api/register-queue): Added a new `realm_playgrounds`
  field, which is required to fetch the set of configured code playgrounds for
  an organization.

**Feature level 48**

* [`POST /users/me/muted_users/{muted_user_id}`](/api/mute-user),
  [`DELETE /users/me/muted_users/{muted_user_id}`](/api/unmute-user):
  New endpoints added to mute/unmute users.
* [`GET /events`](/api/get-events): Added new event type `muted_users`
  which will be sent to a user when the set of users muted by them has
  changed.
* [`POST /register`](/api/register-queue): Added a new `muted_users` field,
  which identifies the set of other users the current user has muted.

**Feature level 47**

* [`POST /register`](/api/register-queue): Added a new `giphy_api_key`
  field, which is required to fetch GIFs using the GIPHY API.

**Feature level 46**

* [`GET /messages`](/api/get-messages) and [`GET
  /events`](/api/get-events): The `topic_links` field now contains a
  list of dictionaries, rather than a list of strings.

**Feature level 45**

* [`GET /events`](/api/get-events): Removed useless `op` field from
  `custom_profile_fields` events.  These events contain the full set
  of configured `custom_profile_fields` for the organization
  regardless of what triggered the change.

**Feature level 44**

* [`POST /register`](/api/register-queue): extended the `unread_msgs`
  object to include `old_unreads_missing`, which indicates whether the
  server truncated the `unread_msgs` due to excessive total unread
  messages.

**Feature level 43**

* [`GET /users/{user_id_or_email}/presence`](/api/get-user-presence):
  Added support for passing the `user_id` to identify the target user.

**Feature level 42**

* `PATCH /settings/display`: Added a new `default_view` setting allowing
  the user to [set the default view](/help/configure-home-view).

**Feature level 41**

* [`GET /events`](/api/get-events): Removed `name` field from update
  subscription events.

**Feature level 40**

* [`GET /events`](/api/get-events): Removed `email` field from update
  subscription events.

**Feature level 39**

* Added new [`GET /users/{email}`](/api/get-user-by-email) endpoint.

**Feature level 38**

* [`POST /register`](/api/register-queue): Increased
  `realm_community_topic_editing_limit_seconds` time limit value
  to 259200s (3 days).

**Feature level 37**

* Consistently provide `subscribers` in stream data when
  clients register for subscriptions with `include_subscribers`,
  even if the user can't access subscribers.

**Feature level 36**

* [`POST /users`](/api/create-user): Restricted access to organization
  administrators with the `can_create_users` permission.
* [Error handling](/api/rest-error-handling): The `code` property will
  now be present in errors due to rate limits.

**Feature level 35**

* [`GET /events`](/api/get-events): The `subscription` events for
  `peer_add` and `peer_remove` now include `user_ids` and `stream_ids`
  arrays. Previously, these events included singular `user_id` and
  `stream_id` integers.

**Feature level 34**

* [`POST /register`](/api/register-queue): Added a new `wildcard_mention_policy`
  setting for controlling who can use wildcard mentions in large streams.

**Feature level 33**

* [Markdown message formatting](/api/message-formatting#code-blocks):
  [Code blocks](/help/code-blocks) now have a `data-code-language`
  attribute attached to the outer HTML `div` element, recording the
  programming language that was selected for syntax highlighting.

**Feature level 32**

* [`GET /events`](/api/get-events): Added `op` field to
  `update_message_flags` events, deprecating the `operation` field
  (which has the same value).  This removes an unintentional anomaly
  in the format of this event type.

**Feature level 31**

* [`GET /users/me/subscriptions`](/api/get-subscriptions): Added a
  `role` field to Subscription objects representing whether the user
  is a stream administrator.

* [`GET /events`](/api/get-events): Added `role` field to
  Subscription objects sent in `subscriptions` events.

Note that as of this feature level, stream administrators are a
partially completed feature.  In particular, it is impossible for a
user to be a stream administrator at this feature level.

**Feature level 30**

* [`GET /users/me/subscriptions`](/api/get-subscriptions), [`GET
  /streams`](/api/get-streams): Added `date_created` to Stream
  objects.
* [`POST /users`](/api/create-user), `POST /bots`: The ID of the newly
  created user is now returned in the response.

Feature levels 28 and 29 are reserved for future use in 3.x bug fix
releases.

## Changes in Zulip 3.1

**Feature level 27**

* [`POST /users`](/api/create-user): Removed `short_name` field from
  `display_recipient` array objects.

**Feature level 26**

* [`GET /messages`](/api/get-messages), [`GET /events`](/api/get-events):
  The `sender_short_name` field is no longer included in message objects
  returned by these endpoints.
* [`GET /messages`](/api/get-messages) : Removed `short_name` field from
  `display_recipient` array objects.

## Changes in Zulip 3.0

**Feature level 25**

No changes; feature level used for Zulip 3.0 release.

**Feature level 24**

* [Markdown message formatting](/api/message-formatting#removed-features):
  The rarely used `!avatar()` and `!gravatar()` markup syntax, which
  was never documented and had inconsistent syntax, was removed.

**Feature level 23**

* `GET/PUT/POST /users/me/pointer`: Removed.  Zulip 3.0 removes the
  `pointer` concept from Zulip; this legacy data structure was
  replaced by tracking unread messages and loading views centered on
  the first unread message.

**Feature level 22**

* [`GET /attachments`](/api/get-attachments): The date when a message
  using the attachment was sent is now correctly encoded as
  `date_sent`, replacing the confusingly named `name` field.  The
  `date_sent` and `create_time` fields of attachment objects are now
  encoded as integers; (previously the implementation could send
  floats incorrectly suggesting that microsecond precision is
  relevant).
* [`GET /invites`](/api/get-invites): Now encodes the user ID of the person
   who created the invitation as `invited_by_user_id`, replacing the previous
   `ref` field (which had that user's Zulip display email address).
* [`POST /register`](/api/register-queue): The encoding of an
  unlimited `realm_message_retention_days` in the response was changed
  from `null` to `-1`.

**Feature level 21**

* `PATCH /settings/display`: Replaced the `night_mode` boolean with
  `color_scheme` as part of supporting automatic night theme detection.

**Feature level 20**

* Added support for inviting users as organization owners to the
  invitation endpoints.

**Feature level 19**

* [`GET /events`](/api/get-events): The `subscription` events for
  `peer_add` and `peer_remove` now identify the modified
  stream by the `stream_id` field, replacing the old `name` field.

**Feature level 18**

* [`POST /register`](/api/register-queue): Added
  `user_avatar_url_field_optional` to supported `client_capabilities`.

**Feature level 17**

* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams): Added
  `message_retention_days` to Stream objects.
* [`POST /users/me/subscriptions`](/api/subscribe), [`PATCH
  /streams/{stream_id}`](/api/update-stream): Added `message_retention_days`
  parameter.

**Feature level 16**

* [`GET /users/me`](/api/get-own-user): Removed `pointer` from the response,
  as the "pointer" concept is being removed in Zulip.
* Changed the rendered HTML markup for mentioning a time to use the
  `<time>` HTML tag.  It is OK for clients to ignore the previous time
  mention markup, as the feature was not advertised before this change.

**Feature level 15**

* [Markdown message formatting](/api/message-formatting#spoilers): Added
  [spoilers](/help/spoilers) to supported message formatting features.

**Feature level 14**

* [`GET /users/me/subscriptions`](/api/get-subscriptions): Removed
  the `is_old_stream` field from Stream objects.  This field was
  always equivalent to `stream_weekly_traffic != null` on the same object.

**Feature level 13**

* [`POST /register`](/api/register-queue): Added
  `bulk_message_deletion` to supported `client_capabilities`.
* [`GET /events`](/api/get-events): `delete_message`
  events have new behavior.  The `sender` and `sender_id` fields were
  removed, and the `message_id` field was replaced by a `message_ids`
  list for clients with the `bulk_message_deletion` client capability.
  All clients should upgrade; we expect `bulk_message_deletion` to be
  required in the future.

**Feature level 12**

* [`GET /users/{user_id}/subscriptions/{stream_id}`](/api/get-subscription-status):
  New endpoint added for checking if another user is subscribed to a stream.

**Feature level 11**

* [`POST /register`](/api/register-queue): Added
  `realm_community_topic_editing_limit_seconds` to the response, the
  time limit before community topic editing is forbidden.  A `null`
  value means no limit. This was previously hard-coded in the server
  as 86400 seconds (1 day).
* [`POST /register`](/api/register-queue): The response now contains
  an `is_owner` boolean field, which is similar to the existing
  `is_admin` and `is_guest` fields.
* [`POST /typing`](/api/set-typing-status): Removed legacy
  support for sending email addresses in the `to` parameter, rather
  than user IDs, to encode direct message recipients.

**Feature level 10**

* [`GET /users/me`](/api/get-own-user): Added `avatar_version`, `is_guest`,
  `is_active`, `timezone`, and `date_joined` fields to the User objects.
* [`GET /users/me`](/api/get-own-user): Removed `client_id` and `short_name`
  from the response to this endpoint.  These fields had no purpose and
  were inconsistent with other API responses describing users.

**Feature level 9**

* [`POST /users/me/subscriptions`](/api/subscribe), [`DELETE
  /users/me/subscriptions`](/api/unsubscribe): Other users to
  subscribe/unsubscribe, declared in the `principals` parameter, can
  now be referenced by user_id, rather than Zulip display email
  address.
* [`PATCH /messages/{message_id}`](/api/update-message): Added
  `send_notification_to_old_thread` and
  `send_notification_to_new_thread` optional parameters.

**Feature level 8**

* [`GET /users`](/api/get-users), [`GET /users/{user_id}`](/api/get-user)
  and [`GET /users/me`](/api/get-own-user): User objects now contain the
  `is_owner` field as well.
* [Markdown message formatting](/api/message-formatting#global-times):
  Added [global times](/help/global-times) to supported message
  formatting features.

**Feature level 7**

* [`GET /events`](/api/get-events): `realm_user` and
  `realm_bot` events no longer contain an `email` field to identify
  the user; use the `user_id` field instead.  Previously, some (but
  not all) events of these types contained an `email` key in addition to
  to `user_id`) for identifying the modified user.
* [`PATCH /users/{user_id}`](/api/update-user): The `is_admin` and
  `is_guest` parameters were removed in favor of the more general
  `role` parameter for specifying a change in user role.
* [`GET /events`](/api/get-events): `realm_user` events
  sent when a user's role changes now include `role` property, instead
  of the previous `is_guest` or `is_admin` booleans.
* [`GET /realm/emoji`](/api/get-custom-emoji): The user who uploaded a
  given custom emoji is now indicated by an `author_id` field, replacing
  a previous `author` object that had unnecessary additional data.

**Feature level 6**

* [`GET /events`](/api/get-events): `realm_user` events to
  update a user's avatar now include the `avatar_version` field, which
  is important for correctly refetching medium-size avatar images when
  the user's avatar changes.
* [`GET /users`](/api/get-users) and [`GET
  /users/{user_id}`](/api/get-user): User objects now contain the
  `avatar_version` field as well.

**Feature level 5**

* [`GET /events`](/api/get-events): `realm_bot` events,
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

**Feature level 3**

* [`POST /register`](/api/register-queue): `zulip_version` and
  `zulip_feature_level` are always returned in the endpoint response.
  Previously, they were only present if `event_types` included
  `zulip_version`.
* Added new `presence_enabled` user notification setting; previously
  [presence](/help/status-and-availability) was always enabled.

**Feature level 2**:

* [`POST /messages/{message_id}/reactions`](/api/add-reaction):
  The `reaction_type` parameter is optional; the server will guess the
  `reaction_type` if it is not specified (checking custom emoji, then
  Unicode emoji for any with the provided name).
* `reactions` objects returned by the API (both in `GET /messages` and
  in `GET /events`) now include the user who reacted in a top-level
  `user_id` field.  The legacy `user` dictionary (which had
  inconsistent format between those two endpoints) is deprecated.

**Feature level 1**:

* [`PATCH /messages/{message_id}`](/api/update-message): Added the
  `stream_id` parameter to support moving messages between streams.
* [`GET /messages`](/api/get-messages), [`GET /events`](/api/get-events):
  Added `prev_stream` as a potential property of the `edit_history` object
  within message objects to indicate when a message was moved to another
  stream.
* [`GET /messages/{message_id}/history`](/api/get-message-history):
  `prev_stream` is present in `snapshot` objects within `message_history`
  object when a message was moved to another stream.
* [`GET /server_settings`](/api/get-server-settings): Added
  `zulip_feature_level`, which can be used by clients to detect which
  of the features described in this changelog are supported.
* [`POST /register`](/api/register-queue): Added `zulip_feature_level`
  to the response if `zulip_version` is among the requested
  `event_types`.
* [`GET /users`](/api/get-users): User objects for bots now
  contain a `bot_owner_id`, replacing the previous `bot_owner` field
  (which had the email address of the bot owner).
* [`GET /users/{user_id}`](/api/get-user): New endpoint added to get
  a single user's details by the user's ID.
* [`GET /messages`](/api/get-messages): Add support for string-format
  values for the `anchor` parameter, deprecating and replacing the
  `use_first_unread_anchor` parameter.
* [`GET /messages`](/api/get-messages), [`GET /events`](/api/get-events):
  Message objects now use `topic_links` rather than `subject_links` to
  indicate links either present in the topic or generated by linkifiers
  applied to the topic.
* [`GET /streams`](/api/get-streams),
  [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Stream objects now
  have `stream_post_policy` enum for specifying who can post to the stream,
  deprecating and replacing the `is_announcement_only` boolean.
* [`GET /user_uploads/{realm_id_str}/{filename}`](/api/get-file-temporary-url):
  New endpoint added for requesting a temporary URL for an uploaded
  file that does not require authentication to access (e.g. for passing
  from a Zulip desktop, mobile, or terminal app to the user's default
  browser).
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  `PATCH /realm`: Nobody added as an option for the realm setting
  `email_address_visibility`.
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  `PATCH /realm`: Added realm setting `private_message_policy`.
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events):
  `muted_topics` array objects now are 3-item tuples that include the
  stream name, the topic name, and the time when the topic was muted.
  Previously, they were 2-item tuples and did not include the time when
  the topic was muted.
* [`GET /server_settings`](/api/get-server-settings): Added `gitlab` boolean
  to deprecated `authentication_methods` object.
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  `PATCH /realm`: None added as an option for the realm setting
  `video_chat_provider` to disable video call UI.

## Changes in Zulip 2.1

* [`POST /register`](/api/register-queue): Added
  `realm_default_external_accounts` to endpoint response.
* [`GET /messages`](/api/get-messages): Added support for
  [search/narrow options](/api/construct-narrow) that use stream/user
  IDs to specify a message's sender, its stream, and/or its recipient(s).
* [`GET /users`](/api/get-users): Added `include_custom_profile_fields`
  to request custom profile field data.
* [`GET /users/me`](/api/get-own-user): Added `avatar_url` field,
  containing the user's avatar URL, to the response.
* [`GET /users/me/subscriptions`](/api/get-subscriptions): Added
  `include_subscribers` parameter controlling whether data on the
  other subscribers is included.  Previous behavior was to always send
  subscriber data.
* [`GET /users/me/subscriptions`](/api/get-subscriptions):
  Stream-level notification settings like `push_notifications` were
  changed to be nullable boolean fields (true/false/null), with `null`
  meaning that the stream inherits the organization-level default.
  Previously, the only values were true/false.  A client communicates
  support for this feature using `client_capabilities`.
* [`GET /users/me/subscriptions`](/api/get-subscriptions): Added
  `wildcard_mentions_notify` notification setting, with the same
  global-plus-stream-level-override model as other notification settings.
* [`GET /server_settings`](/api/get-server-settings): Added
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
* [`POST /users/me/subscriptions/properties`](/api/update-subscription-settings):
  Deprecated `in_home_view`, replacing it with the more readable
  `is_muted` (with the opposite meaning).
* Custom profile fields: Added `EXTERNAL_ACCOUNT` field type.

## Changes in Zulip 2.0

* [`PATCH /users/me/subscriptions/muted_topics`](/api/mute-topic):
  Added support for using stream IDs to specify the stream in which to
  mute/unmute a topic.
* [`POST /messages`](/api/send-message): Added support for using user
  IDs and stream IDs for specifying the recipients of a message.
* [`POST /messages`](/api/send-message), [`POST
  /messages/{message_id}`](/api/update-message): Added support for
  encoding topics using the `topic` parameter name.  The previous
  `subject` parameter name was deprecated but is still supported for
  backwards-compatibility.
* [`POST /typing`](/api/set-typing-status): Added support for specifying the
  recipients with user IDs, deprecating the original API of specifying
  them using email addresses.

------------------

## Changes not yet stabilized

* [`POST /register`](/api/register-queue): Added `slim_presence`
  parameter.  Changes the format of presence events, but is still
  being changed and should not be used by clients.

[server-changelog]: https://zulip.readthedocs.io/en/latest/overview/changelog.html
[release-lifecycle]: https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html
[rfc6570]: https://www.rfc-editor.org/rfc/rfc6570.html
