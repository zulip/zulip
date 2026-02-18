* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue):
  Removed `api_key` field from bot objects.
* [`GET /events`](/api/get-events): `realm_bot/update` event is no longer
  sent when a bot's api key is regenerated.
* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue):
  Removed `avatar_url`, `bot_type`, `email`, `full_name`, `is_active` and
  `owner_id` fields from bot objects.
* [`GET /events`](/api/get-events): `realm_bot/update` event is no longer
  sent when updating a bot's avatar, email, name, or owner and also when
  deactivating or reactivating a bot.
