**Feature level ZF-d9af1a**

* [`POST /register`](/api/register-queue): The `user_topics` data now
  includes entries for topics in archived channels for clients that
  declared the `archived_channels`
  [client capability](/api/register-queue#parameter-client_capabilities).
  Previously, such entries were always excluded, even though the
  server continued to apply those visibility policies when computing
  unread counts and after the channel was unarchived.
