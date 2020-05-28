# Message retention policy (beta)

By default, Zulip stores messages indefinitely, allowing full-text
search of your complete history.

Zulip supports configuring both a global organization-level message
retention policy, as well as retention policies for individual
streams.  These policies control how many days a message is stored
before being automatically deleted (the default being forever).
Zulip's system supports:

* Setting a retention policy for individual streams, to just delete
  messages on those specific streams.
* Setting an organization-level policy, and a "forever" policy for
  specific streams, to preserve messages indefinitely on those
  streams, while automatically deleting both PMs and messages sent to
  other streams.

In Zulip Cloud, message retention policies are available on the Zulip
Cloud Standard and Zulip Cloud Plus [plans](https://zulip.com/plans),
as well as for the hundreds of communities with sponsored Cloud
Standard hosting.  Contact support@zulip.com if you're on one of
these plans and would like to enable it.

## Important details

* Retention policies are processed in a daily job; so changes in the
  policy won't have any effect until the next time the daily job runs.

* Deleted messages are preserved temporarily in a special archive.  So
if you discover a misconfiguration accidentally deleted content you
meant to preserve, contact Zulip support promptly for assistance with
restoration.  See the [deletion
documentation](/help/edit-or-delete-a-message#how-deletion-works) for
more details on precisely how message deletion works in Zulip.

## Related articles

* [Edit or delete a message](/help/edit-or-delete-a-message)
* [Delete a topic](/help/delete-a-topic)
* [Delete a stream](/help/delete-a-stream)
