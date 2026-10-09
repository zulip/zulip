* [`POST /register`](/api/register-queue), [`PATCH /settings`](/api/update-settings),
  [`PATCH /realm/user_settings_defaults`](/api/update-realm-user-settings-defaults):
  Added new `web_left_sidebar_topics_order` display setting, controlling
  whether the web/desktop application's left sidebar lists a channel's
  resolved topics after its unresolved ones.

* [`POST /users/me/subscriptions/properties`](/api/update-subscription-settings),
  [`PATCH /users/me/subscriptions/{stream_id}`](/api/update-subscription-property),
  [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events):
  Added `web_left_sidebar_topics_order` subscription property, a per-channel
  override of the user setting of the same name. The subscription properties
  endpoints now accept an integer `value` for it.
