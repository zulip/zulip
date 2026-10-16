* [`GET /events`](/api/get-events): `realm/update_dict` and `user_group/update`
  events are no longer sent upon user reactivation.
* [`GET /events`](/api/get-events): `realm/update_dict` and `user_group/update`
  events are now sent to all users in the organization upon user deactivation.
* [`GET /events`](/api/get-events): To ensure that
  [group-setting values](/api/group-setting-values) are correct,
  `stream/update` events may now be by sent by the server when
  processing deactivation of a user to all users in the organization,
  to ensure client state correctly reflects the state, given that
  deactivated users cannot have permissions in an organization.
