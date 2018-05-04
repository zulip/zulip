# Guest users

This page documents how guest users work in Zulip.  This documentation
attempts to cover the current state first, and then the
to-be-implemented restrictions.

Guest users are like normal users in Zulip, except that they cannot do
the following:

* Join public streams without being added by another user.
* Access message history on public streams.
* Create streams (public or private)
* Create or own bots users

For many of these limitations, we haven't yet hidden the relevant
section(s) of the UI, and the prototype guest user experience will
feel buggy until we hide those features.

Limitations to be implemented:
* Manage streams (e.g. Add other users to a stream they are subscribed
  to)
* See streams they are not subscribed to.
* Interact with user groups
* Send private messages to users not in a stream with them.

(And more, this is an initial high-level TODO list).

