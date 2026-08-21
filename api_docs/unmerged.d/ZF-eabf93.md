
* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  `PATCH /realm`: Google Meet OAuth integration added as an option
  for the realm setting `video_chat_provider`.
* [`POST /calls/google_meet/create`](/api/create-google-meet-video-call): Added
  a new endpoint to create a Google Meet video call URL.
* [`POST /register`](/api/register-queue): Added `has_google_meet_token`
  boolean field to response.
* [`GET /events`](/api/get-events): A `has_google_meet_token` event is sent
  to clients when the user has completed the OAuth flow for the Google Meet
  video call integration.
* [`POST /register`](/api/register-queue): Added
  `server_video_google_meet_app_internal` boolean field, indicating whether
  the server's Google Cloud OAuth app is configured with an Internal
  (Workspace-restricted) audience.
