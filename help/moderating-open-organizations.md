# Moderating open organizations

An **open organization** is one where
[anyone can join without an invitation](/help/restrict-account-creation#set-whether-invitations-are-required-to-join).
Moderation is a big part of making an open community work.

## Prevention

Zulip has many features designed to simplify moderation by preventing
problematic behavior:

* [Disallow disposable email addresses](/help/restrict-account-creation#dont-allow-disposable-domains)
  or [require users to log in via GitHub or GitLab](/help/configure-authentication-methods).
* Restrict who can [create streams](/help/configure-who-can-create-streams),
  [create bots](/help/restrict-bot-creation), [send direct
  messages](/help/restrict-direct-messages), or
  [add custom emoji](/help/custom-emoji#change-who-can-add-custom-emoji).
* Link to a code of conduct in your
  [organization description](/help/create-your-organization-profile)
  (displayed on the registration page).
* Create a [default stream](/help/set-default-streams-for-new-users)
  for announcements where [only admins can
  post](/help/stream-sending-policy).
* Add a [waiting period](/help/restrict-permissions-of-new-members) before
  new users can take disruptive actions.
* [Configure email visibility](/help/configure-email-visibility)
  to prevent off-platform spam.
* [Restrict wildcard mentions](/help/restrict-wildcard-mentions)
  so only [moderators](/help/roles-and-permissions) can mention everyone in your organization.

## Response

The following features are an important part of an organization's
playbook when responding to abuse or spam that is not prevented by the
organization's policy choices.

* Individual users can [mute abusive users](/help/mute-a-user) to stop
  harassment that moderators have not yet addressed, or [collapse
  individual messages](/help/collapse-a-message) that they don't want
  to see.
* [Ban (deactivate) users](/help/deactivate-or-reactivate-a-user) acting in
  bad faith. You can reactivate them later if they repent.
* Investigate behavior using the `streams:public
  sender:user@example.com` [search
  operators](/help/search-for-messages) to find all messages sent by a
  user.
* Delete messages, [archive streams](/help/archive-a-stream), and
  [unsubscribe users from streams](/help/add-or-remove-users-from-a-stream).
* [Move topics](/help/rename-a-topic), including between streams, when
  users start conversations in the wrong place.
* [Change users' names](/help/change-a-users-name) (e.g. to "Name (Spammer)")
  for users who sent spam direct messages to many community members.
* [Deactivate bots](/help/deactivate-or-reactivate-a-bot) or
  [deactivate custom emoji](/help/custom-emoji#deactivate-custom-emoji).

## Public access option

{!web-public-streams-intro.md!}

## Zulip communities directory

{!communities-directory-intro.md!}

For details on how to get your community listed, see [Communities
directory](/help/communities-directory).

## Related articles

* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Public access option](/help/public-access-option)
* [Communities directory](/help/communities-directory)
