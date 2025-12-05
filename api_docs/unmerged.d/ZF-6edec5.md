* [`GET /events`](/api/get-events), [`POST /register`](/api/register-queue),
  [`GET /users/{user_id}/status`](/api/get-user-status): Added new `scheduled_end_time`
  field to the `user_status` object to schedule time to automatically clear the status.
* [`POST /users/me/status`](/api/update-status): Added support for new
  `scheduled_end_time` parameter to schedule time to automatically clear
  the status.
