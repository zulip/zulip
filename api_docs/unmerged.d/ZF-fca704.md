* `PATCH /realm`: Replaced the `name_changes_disabled` boolean setting with
  the `can_change_own_name_group` [group-setting value](/api/group-setting-values)
  for controlling which users can change their own names.
* `POST /register` and `GET /events`: Replaced the
  `realm_name_changes_disabled` field with the
  `realm_can_change_own_name_group` [group-setting value](/api/group-setting-values)
  in organization data.
