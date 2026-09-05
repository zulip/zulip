* [`GET /users`](/api/get-users), [`GET /users/{user_id}`](/api/get-user),
  [`GET /users/{email}`](/api/get-user-by-email), [`GET
  /events`](/api/get-events), [`POST /register`](/api/register-queue):
  Added `avatar_source` to user objects.

* [`POST /users/{user_id}/avatar`](/api/upload-avatar-for-user),
  [`DELETE /users/{user_id}/avatar`](/api/delete-avatar-for-user): Added
  new endpoints allowing administrators to upload and delete another
  user's profile picture. Unlike the corresponding `/users/me/avatar`
  endpoints, these can be used in organizations that restrict profile
  picture changes, and support targeting deactivated users.
