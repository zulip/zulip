**Feature level ZF-9dad35**

* [`POST /users/me/dm_conversations/pin`](/api/update-dm-conversation-pin):
  Added a new endpoint to pin or unpin a direct message conversation to
  the top of the "Direct messages" section in the left sidebar.
* [`POST /register`](/api/register-queue): Each object in the
  `recent_private_conversations` array now includes a `pinned` boolean
  indicating whether the current user has pinned that direct message
  conversation.
* [`GET /events`](/api/get-events): Added a new
  `direct_message_conversation` event, sent to a user when they pin or
  unpin a direct message conversation.
