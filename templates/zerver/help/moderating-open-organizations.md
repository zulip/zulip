# Moderating open organizations

An **open organization** is one where
[anyone can join without an invitation](/help/allow-anyone-to-join-without-an-invitation).
Moderation is a big part of making an open community work.

## Prevention

* [Disallow disposable email addresses](/help/allow-anyone-to-join-without-an-invitation)
  or [require users to log in via GitHub](/help/configure-authentication-methods).
* Restrict who can [create streams](/help/configure-who-can-create-streams),
  [create bots](/help/restrict-bot-creation) or
  [add custom emoji](/help/only-allow-admins-to-add-emoji).
* Link to a code of conduct in your
  [organization description](/help/create-your-organization-profile)
  (displayed on the registration page).
* Create at least one
  [default stream](/help/set-default-streams-for-new-users) where
  [only admins can post](/help/announcement-only-streams).
* Add a [waiting period](/help/restrict-permissions-of-new-members) before
  new users can take disruptive actions.
* [Restrict email visibility](/help/restrict-visibility-of-email-addresses)
  to reduce the likelihood of off-platform spam.

## Response

* [Ban (deactivate) users](/help/deactivate-or-reactivate-a-user) acting in
  bad faith. You can reactivate them later if they repent.
* Use the `streams:public sender:user@example.com`
  [search operators](/help/search-for-messages) to find all messages sent by a user.
* Delete messages, [delete streams](/help/delete-a-stream), and
  [unsubscribe users from streams](/help/add-or-remove-users-from-a-stream).
* [Rename topics](/help/rename-a-topic).
* [Change users' names](/help/change-a-users-name) (e.g. to "Spammer")
* [Deactivate bots](/help/deactivate-or-reactivate-a-bot) or
  [delete custom emoji](/help/add-custom-emoji#delete-custom-emoji).
* Instruct users to [collapse](/help/collapse-a-message) messages that they don't
  want to see.

## In the works

* **Delete spammer**. This will wipe the user from your Zulip, by deleting
  all their messages and reactions, banning them, etc.
* **Mute user**. This will allow an individual user to hide the messages of
  another individual user.
* **New users join as guests**. This will allow users joining via open
  registration to have extremely limited permissions by default, but still
  enough permissions to ask the core team a question or to get a feel for your
  community.
* **Public archive**. This will give a read-only view of selected streams,
  removing the need in some organizations for having open registration.
