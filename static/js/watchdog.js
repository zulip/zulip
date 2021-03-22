const unsuspend_callbacks = [];
let watchdog_time = Date.now();

/*
    Our watchdog code checks every 5 seconds to make sure that we
    haven't gone 20 seconds since the last "5-second-ago" check.
    This sounds confusing, but it is just is a way to detect that
    the machine has gone to sleep.

    When we detect the condition we call back to server_events code
    to reset ourselves accordingly.
*/

export function check_for_unsuspend() {
    const new_time = Date.now();
    if (new_time - watchdog_time > 20000) {
        // 20 seconds.
        // Defensively reset watchdog_time here in case there's an
        // exception in one of the event handlers
        watchdog_time = new_time;
        // Our app's JS wasn't running, which probably means the machine was
        // asleep.
        for (const callback of unsuspend_callbacks) {
            callback();
        }
    }
    watchdog_time = new_time;
}

export function on_unsuspend(f) {
    unsuspend_callbacks.push(f);
}

setInterval(check_for_unsuspend, 5000);
