# Removing sent notifications from mobile as messages read on server

How to remove notifications from server to mobile

For iOS:

Call `removeDeliveredNotifications(withIdentifiers identifiers:
[String])` The main identifiers here would be the message id to search
for the notifications in the Notification center A background update
notification will be sent from the server containing the payload,
which would trigger
`application:didReceiveRemoteNotification:fetchCompletionHandler` here
we can call the removeDeliveredNotifications.

Important quotes from docs.

> To support a background update notification, make sure that the
  payload’s aps dictionary includes the content-available key with a
  value of 1. If there are user-visible updates that go along with the
  background update, you can set the alert, sound, or badge keys in
  the aps dictionary, as appropriate.

> When a background update notification is delivered to the user’s
  device, iOS wakes up your app in the background and gives it up to
  30 seconds to run. In iOS, the system delivers background update
  notifications by calling the
  application:didReceiveRemoteNotification:fetchCompletionHandler:
  method of your app delegate. Use that method to initiate any
  download operations needed to fetch new data. Processing remote
  notifications in the background requires that you add the
  appropriate background modes to your app.

References:

[removeDeliveredNotifications]: https://developer.apple.com/documentation/usernotifications/unusernotificationcenter/1649500-removedeliverednotifications

[Notification Payload]: https://developer.apple.com/library/archive/documentation/NetworkingInternet/Conceptual/RemoteNotificationsPG/CreatingtheNotificationPayload.html#//apple_ref/doc/uid/TP40008194-CH10-SW8

For Android:

Send the a gcm message containing message id and a key named `event` with the
value of `remove`. The current data structure in the client app saves the list
of messages (containing content and message id) grouped by narrow in a `LinkedHashMap`.

So there can be two cases, the notification to be removed can be either the

- Last one - Remove the full conversation as if the last message is
  read then the previous ones are read also.
- Before the last message - Remove this message from the list.
