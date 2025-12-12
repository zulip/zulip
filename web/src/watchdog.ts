import * as blueslip from "./blueslip.ts";

const unsuspend_callbacks: (() => void)[] = [];
let watchdog_time = Date.now();

// This field keeps track of whether we are attempting to
// force-reconnect to the events server due to suspecting we are
// offline.  It is important for avoiding races with the presence
// system when coming back from unsuspend.
let suspect_offline = false;

export function set_suspect_offline(suspected: boolean): void {
    suspect_offline = suspected;
}

export function suspects_user_is_offline(): boolean {
    return suspect_offline;
}

/*
    Our watchdog code checks every 5 seconds to make sure that we
    haven't gone 20 seconds since the last "5-second-ago" check.
    This sounds confusing, but it is just is a way to detect that
    the machine has gone to sleep.

    When we detect the condition we call back to server_events code
    to reset ourselves accordingly.
*/

export function check_for_unsuspend(): void {
    const new_time = Date.now();
    if (new_time - watchdog_time > 20000) {
        // 20 seconds.
        // Defensively reset watchdog_time here in case there's an
        // exception in one of the event handlers
        watchdog_time = new_time;
        // Our app's JS wasn't running, which probably means the machine was
        // asleep.
        for (const callback of unsuspend_callbacks) {
            try {
                callback();
            } catch (error) {
                blueslip.error(
                    `Error while executing callback '${
                        callback.name || "Anonymous function"
                    }' from unsuspend_callbacks.`,
                    undefined,
                    error,
                );
            }
        }
    }
    watchdog_time = new_time;
}

export function on_unsuspend(f: () => void): void {
    unsuspend_callbacks.push(f);
}

setInterval(check_for_unsuspend, 5000);

// The Page Lifecycle API "resume" event.
// This handles when the page is "resumed" from a frozen state, such as when
// the user switches back to a tab that Chrome has discarded/frozen to save memory.
//
// We check for `document` existence to avoid breaking Node.js-based tests that
// import this module but don't implement the full DOM API.
if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
    document.addEventListener("resume", () => {
        check_for_unsuspend();
    });
}

// The BFCache "pageshow" event.
// This handles when the page is restored from the Back-Forward Cache (BFCache),
// e.g. when the user navigates back to this page.
// We check for `event.persisted` to ensure we only trigger on a restore, not a fresh load.
if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) {
            check_for_unsuspend();
        }
    });
}
