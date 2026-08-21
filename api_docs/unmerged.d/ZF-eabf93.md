
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
  `server_google_meet_app_internal` boolean field the response, indicating
  whether the server has a Google Cloud OAuth app configured with an internal,
  workspace-restricted, audience. Clients should use this to warn users that
  the video call feature is restricted to a particular Google Workspace before
  starting the Google OAuth flow for the Google Meet video call integration.
