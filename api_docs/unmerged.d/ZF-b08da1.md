* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  `PATCH /realm`: Webex OAuth integration added as an option
  for the realm setting `video_chat_provider`.
* [`POST /calls/webex/create`](/api/create-webex-video-call): Added
  a new endpoint to create a Webex video call URL.
* [`POST /register`](/api/register-queue): Added `has_webex_token`
  boolean field to response.
* [`GET /events`](/api/get-events):  A `has_webex_token` event is sent
  to clients when the user has completed the OAuth flow for the Webex
  video call integration.
