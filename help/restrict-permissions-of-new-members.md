# Restrict permissions of new members

{!owner-only.md!}

In large Zulip organizations where
[anyone can join](/help/restrict-account-creation#set-whether-invitations-are-required-to-join), it can
be useful to restrict what new members can do, to make it easier to cope
with spammers and confused users.

Members are **new members** from when they join till when their account ages
past a certain **waiting period** threshold. After that they are **full members**.
You can configure how long the waiting period is, as well as which actions require
being a full member.

For some features, Zulip supports restricting access to only full members. These
features include [creating channels](/help/configure-who-can-create-channels),
[inviting users to the organization](/help/invite-new-users),
[adding custom emoji](/help/custom-emoji#change-who-can-add-custom-emoji),
and many more.

## Set waiting period for new members

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Joining the organization**, configure
   **Waiting period before new members turn into full members**.

{!save-changes.md!}

{end_tabs}

## Related articles

- [Roles and permissions](/help/roles-and-permissions)
