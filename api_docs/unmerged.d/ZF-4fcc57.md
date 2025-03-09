* [`PATCH /settings`](/api/update-settings): Added support for bulk updates to
  settings for specified users or members of user groups. When invoked by a
  realm owner, the endpoint now supports the `target_users` parameter to specify
  which users and user groups to update, and the `skip_if_already_edited`
  parameter to optionally skip updating a user's setting if it has been
  previously modified by the user.
