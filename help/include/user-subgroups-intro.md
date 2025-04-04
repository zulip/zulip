You can add a group to another user group, making it easy to express your
organization's structure in Zulip's permissions system. A user who belongs to a
subgroup of a group is treated as a member of that group. For example:

- The “engineering” group could be made up of “engineering-managers” and
  “engineering-staff”.
- The “managers” group could be made up of “engineering-managers”,
  “design-managers”, etc.

Updating the members of a group automatically updates the members of all the
groups that contain it. In the above example, adding a new team member to
“engineering-managers” automatically adds them to “engineering” and “managers”
as well. Removing a team member who transferred automatically removes them.
