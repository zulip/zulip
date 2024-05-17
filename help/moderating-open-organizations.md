# Moderating open organizations

An **open organization** is one where
[anyone can join without an invitation](/help/restrict-account-creation#set-whether-invitations-are-required-to-join).
Moderation is a big part of making an open community work.

## Prevention

Zulip has many features designed to simplify moderation by preventing
problematic behavior.

### Manage new users

* Link to a code of conduct in your
  [organization description](/help/create-your-organization-profile)
  (displayed on the registration page).
* [Disallow disposable email
  addresses](/help/restrict-account-creation#dont-allow-disposable-domains)
  or [limit authentication
  methods](/help/configure-authentication-methods) to increase the
  effort for a bad actor to replace a banned account.
* Add a [waiting period](/help/restrict-permissions-of-new-members) before
  new users can take disruptive actions.
* Monitor new users by enabling [new user
  announcements](/help/configure-automated-notices#new-user-announcements).

### Restrict permissions for making changes

* Restrict who can [create channels](/help/configure-who-can-create-channels), or
  monitor new channels by enabling [new channel
  announcements](/help/configure-automated-notices#new-channel-announcements).
* Restrict who can [add custom emoji](/help/custom-emoji#change-who-can-add-custom-emoji).
* Restrict who can [move messages to another
  channel](/help/restrict-moving-messages#configure-who-can-move-messages-to-another-channel),
  and set a [time
  limit](/help/restrict-moving-messages#set-a-time-limit-for-editing-topics) for
  editing topics.
* Restrict who can
  [edit](/help/restrict-message-editing-and-deletion#configure-message-editing-permissions)
  and
  [delete](/help/restrict-message-editing-and-deletion#configure-message-deletion-permissions)
  their own messages, and set time limits on message editing and deletion.
* If you are concerned about impersonation, you can [prevent users from changing
  their name](/help/restrict-name-and-email-changes#restrict-name-changes), or
  [require unique
  names](/help/restrict-name-and-email-changes#require-unique-names).

### Minimize spam

* [Configure email visibility](/help/configure-email-visibility)
  to prevent off-platform spam.
* [Restrict wildcard mentions](/help/restrict-wildcard-mentions)
  so only [moderators](/help/roles-and-permissions) can mention everyone in your organization.
* Create a [default channel](/help/set-default-channels-for-new-users)
  for announcements where [only admins can
  post](/help/channel-posting-policy).
* Restrict who can [send direct messages](/help/restrict-direct-messages).

## Response

The following features are an important part of an organization's
playbook when responding to abuse or spam that is not prevented by the
organization's policy choices.

* Individual users can [mute abusive users](/help/mute-a-user) to stop
  harassment that moderators have not yet addressed, or [collapse
  individual messages](/help/collapse-a-message) that they don't want
  to see.
* [Ban (deactivate) users](/help/deactivate-or-reactivate-a-user) acting in bad
  faith. They will not be able to rejoin using the same email address, unless
  their account is reactivated by an administrator.
* Investigate behavior by [viewing messages sent by a
  user](/help/view-messages-sent-by-a-user).
* Delete messages, [archive channels](/help/archive-a-channel), and
  [unsubscribe users from channels](/help/add-or-remove-users-from-a-channel).
* [Move topics](/help/rename-a-topic), including between channels, when
  users start conversations in the wrong place.
* [Change users' names](/help/change-a-users-name) (e.g., to "Name (Spammer)")
  for users who sent spam direct messages to many community members.
* [Deactivate bots](/help/deactivate-or-reactivate-a-bot) or
  [deactivate custom emoji](/help/custom-emoji#deactivate-custom-emoji).

## Public access option

{!web-public-channels-intro.md!}

## Zulip communities directory

{!communities-directory-intro.md!}

For details on how to get your community listed, see [Communities
directory](/help/communities-directory).

## Related articles

* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Public access option](/help/public-access-option)
* [Communities directory](/help/communities-directory)
