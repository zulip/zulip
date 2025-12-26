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

/**
 * Clears the internal state of the watchdog module.
 *
 * This is used by tests to ensure a clean slate between test cases,
 * since the module is not reloaded.
 */
export function _reset_for_testing(): void {
    unsuspend_callbacks.length = 0;
    watchdog_time = Date.now();
    suspect_offline = false;
}

/*
There are two ways for us to detect that the web app had been on a
suspended device. The first is the `resume` event on Document, which
is not yet available on Safari. See
https://caniuse.com/mdn-api_document_resume_event.

So we instead use a timer, and check if more time passed than would be
possible if we were running the whole time. This logic has to be
careful to avoid mishandling the Chrome intensive throttling feature:
https://developer.chrome.com/blog/timer-throttling-in-chrome-88#intensive_throttling

Essentially, for an idle tab, Chromium will eventually start batching
timer events to only run once per minute. We don't want this watchdog
code to trigger every minute in this situation, it's important for
MINIMUM_SUSPEND_MILLISECONDS to be longer than that.

We need CHECK_FREQUENCY_MILLISECONDS to be fairly short, because that
controls how long after unsuspend (and potentially the user focusing
the app) that we might fail to discover that the device has
unsuspended.
*/

const CHECK_FREQUENCY_MILLISECONDS = 5000;
const MINIMUM_SUSPEND_MILLISECONDS = 75000;

export function check_for_unsuspend(): void {
    const new_time = Date.now();
    if (new_time - watchdog_time > MINIMUM_SUSPEND_MILLISECONDS) {
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

export function initialize(): void {
    setInterval(check_for_unsuspend, CHECK_FREQUENCY_MILLISECONDS);

    // The Page Lifecycle API "resume" event.
    // This handles when the page is "resumed" from a frozen state, such as when
    // the user switches back to a tab that Chrome has discarded/frozen to save memory.
    // Note: This event is currently only available on Chrome.
    // See https://developer.chrome.com/docs/web-platform/page-lifecycle-api#event-resume
    document.addEventListener("resume", () => {
        check_for_unsuspend();
    });

    // The BFCache "pageshow" event.
    // This handles when the page is restored from the Back-Forward Cache (BFCache),
    // e.g. when the user navigates back to this page.
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) {
            check_for_unsuspend();
        }
    });
}
