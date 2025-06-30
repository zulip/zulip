* [`GET /events`](/api/get-events):
  Added `reminders` events sent to clients when a user creates
  or deletes scheduled messages.
* [`GET /reminders`](/api/get-reminders):
  Clients can now request `/reminders` endpoint to fetch all
  scheduled reminders.
* [`DELETE /reminders/{reminder_id}`](/api/delete-reminder):
  Clients can now delete a scheduled reminder.
