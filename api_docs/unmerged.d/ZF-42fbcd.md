* [`POST /register_client_device`](/api/register-client-device):
  Added a new endpoint to register a logged-in device.
* [`POST /register`](/api/register-queue): Added `devices`
  field to response.
* [`GET /events`](/api/get-events):  A `device` event is sent
  to clients to live-update the `devices` dictionary.
