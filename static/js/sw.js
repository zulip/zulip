self.addEventListener('notificationclick', function (event) {
    var clickedNotification = event.notification;
    clickedNotification.close();

    // This looks to see if the current is already open and
    // focuses if it is
    event.waitUntil(
        /* eslint-disable no-undef */
        clients.matchAll({
            includeUncontrolled: true,
            type: "window",
        })
        .then(function (clientList) {  
            for (var i = 0; i < clientList.length; i + 1) {
                var client = clientList[i];
                if ('focus' in client) {
                    // Do something as the result of the notification click
                    // TODO: how to get access feature_flags and narrow variables here?
                    // if (feature_flags.clicking_notification_causes_narrow) {
                        // narrow.by_subject(message.id, {trigger: 'notification'});
                    // }
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow('/');
            }
        })
        /* eslint-enable no-undef */
    );
});
