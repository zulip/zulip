**Feature level ZF-35ca3e**

* [`POST /messages/restore`](/api/restore-messages): Added a new endpoint
  to undo a recent deletion, restoring a set of messages from the archive.
  A user can only restore messages they deleted themselves, and only within
  a short server-defined window after the deletion.
* [`GET /events`](/api/get-events): Added a new `restored_message` event,
  sent to a message's original recipients when a deletion is undone, so that
  clients can re-display the restored messages.
