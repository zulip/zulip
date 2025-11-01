* Replaced the `pm_users` field with `recipient_user_ids` in
[E2EE mobile push notifications payload](/api/mobile-notifications)
for group direct message. Previously, `pm_users` was included only
for group DMs; `recipient_user_ids` is present for both 1:1 and
group DM conversations.
