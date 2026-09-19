**Feature level ZF-31a8cd**

* [`POST /users/me/subscriptions`](/api/subscribe), [`PATCH
  /streams/{stream_id}`](/api/update-stream), [`POST
  /channel_folders/create`](/api/create-channel-folder), [`PATCH
  /channel_folders/{channel_folder_id}`](/api/update-channel-folder):
  A channel or channel folder description that mentions a user group
  which the acting user is not allowed to mention is now rejected,
  matching the behavior when sending a message.
