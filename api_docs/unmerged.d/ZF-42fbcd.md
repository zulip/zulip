* [`POST /register_client_device`](/api/register-client-device):
  Added a new endpoint to register a logged-in device.
* [`POST /register`](/api/register-queue): Added `devices`
  field to response.
* [`GET /events`](/api/get-events):  A `device` event is sent
  to clients to live-update the `devices` dictionary.
* [`POST /mobile_push/register`](register-push-device): Redesigned
  the endpoint to support rotation of `push_key` and FCM/APNs provided token.
* [`POST /remotes/push/e2ee/register`](/api/register-remote-push-device):
  Replaced `push_account_id` with `token_id` to support rotation
  of `push_key` and FCM/APNs provided token.
