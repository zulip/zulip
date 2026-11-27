* [`GET /invites/{invite_id}`](/api/get-email-invite-details): New endpoint that
  returns details for a single email invitation, including the `stream_ids` and
  `group_ids` of the channels and groups the invitee will be subscribed to.
* [`GET /invites/multiuse/{invite_id}`](/api/get-multiuse-invite-details): New
  endpoint that returns details for a single reusable invitation link, including
  the `stream_ids` and `group_ids` of the channels and groups the invitee will
  be subscribed to.
