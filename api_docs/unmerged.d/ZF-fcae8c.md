* [`POST /channel_folders/create`](/api/create-channel-folder),
  [`GET /channel_folders`](/api/get-channel-folders),
  [`PATCH /channel_folders/{channel_folder_id}`](/api/update-channel-folder):
  Added a new field `order` to show in which order should channel folders be
  displayed. The list is 0-indexed and works similar to the `order` field of
  custom profile fields.
* [`PATCH /channel_folders`](/api/patch-channel-folders): Added a new
  endpoint for reordering channel folders. It accepts an array of channel
  folder IDs arranged in the order the user desires it to be in.
