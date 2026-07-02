**Feature level ZF-bbdbb7**

* [`POST /messages/{message_id}/edit_history/delete_content_revisions`](/api/delete-message-edit-history-content-revisions):
  New endpoint to delete all prior content revisions from a message's
  edit history. The record that the message was edited is preserved.
  Users with permission to delete a message also have permission to
  delete its edit history; the realm's message deletion time limit does
  not apply to this endpoint.
* [`GET /messages/{message_id}/history`](/api/get-message-history):
  Added `revision_deleted_by` (integer user ID) and `revision_deleted_at`
  (Unix timestamp) fields to history snapshot objects. These fields are
  present on content-edit entries whose previous content has been
  removed via the new endpoint above.
* [`GET /events`](/api/get-events): A new `message_edit_history` event
  with `op: "delete"` is sent when content revisions are deleted from
  a message's edit history.
