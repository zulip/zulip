import _ from "lodash";
import assert from "minimalistic-assert";

type TypingStatusWorker = {
    get_current_time: () => number;
    notify_server_start: (recipient_ids: number[]) => void;
    notify_server_stop: (recipient_ids: number[]) => void;
};

type TypingStatusState = {
    current_recipient_ids: number[];
    next_send_start_time: number;
    idle_timer: ReturnType<typeof setTimeout>;
};

// The following constants are tuned to work with
// TYPING_STARTED_EXPIRY_PERIOD, which is what the other
// users will use to time out our messages.  (Or us,
// depending on your perspective.) See typing_events.js.

// How frequently 'still typing' notifications are sent
// to extend the expiry
const TYPING_STARTED_WAIT_PERIOD = 10000; // 10s
// How long after someone stops editing in the compose box
// do we send a 'stopped typing' notification
const TYPING_STOPPED_WAIT_PERIOD = 5000; // 5s

/** Exported only for tests. */
export let state: TypingStatusState | null = null;

/** Exported only for tests. */
export function stop_last_notification(worker: TypingStatusWorker): void {
    assert(state !== null, "State object should not be null here.");
    clearTimeout(state.idle_timer);
    worker.notify_server_stop(state.current_recipient_ids);
    state = null;
}

/** Exported only for tests. */
export function start_or_extend_idle_timer(
    worker: TypingStatusWorker,
): ReturnType<typeof setTimeout> {
    function on_idle_timeout(): void {
        // We don't do any real error checking here, because
        // if we've been idle, we need to tell folks, and if
        // our current recipients has changed, previous code will
        // have stopped the timer.
        stop_last_notification(worker);
    }

    if (state?.idle_timer) {
        clearTimeout(state.idle_timer);
    }
    return setTimeout(on_idle_timeout, TYPING_STOPPED_WAIT_PERIOD);
}

function set_next_start_time(current_time: number): void {
    assert(state !== null, "State object should not be null here.");
    state.next_send_start_time = current_time + TYPING_STARTED_WAIT_PERIOD;
}

function actually_ping_server(
    worker: TypingStatusWorker,
    recipient_ids: number[],
    current_time: number,
): void {
    worker.notify_server_start(recipient_ids);
    set_next_start_time(current_time);
}

/** Exported only for tests. */
export function maybe_ping_server(worker: TypingStatusWorker, recipient_ids: number[]): void {
    assert(state !== null, "State object should not be null here.");
    const current_time = worker.get_current_time();
    if (current_time > state.next_send_start_time) {
        actually_ping_server(worker, recipient_ids, current_time);
    }
}

/**
 * Update our state machine, and the server as needed, on the user's typing status.
 *
 * This can and should be called frequently, on each keystroke.  The
 * implementation sends "still typing" notices at an appropriate throttled
 * rate, and keeps a timer to send a "stopped typing" notice when the user
 * hasn't typed for a few seconds.
 *
 * Zulip supports typing notifications only for both 1:1 and group direct messages;
 * so composing a stream message should be treated like composing no message at
 * all.
 *
 * Call with `new_recipient_ids` of `null` when the user actively stops
 * composing a message.  If the user switches from one set of recipients to
 * another, there's no need to call with `null` in between; the
 * implementation tracks the change and behaves appropriately.
 *
 * See docs/subsystems/typing-indicators.md for detailed background on the
 * typing indicators system.
 *
 * @param {*} worker Callbacks for reaching the real world. See typing.js
 *   for implementations.
 * @param {*} new_recipient_ids The users the direct message being composed is
 *   addressed to, as a sorted array of user IDs; or `null` if no direct message
 *   is being composed anymore.
 */
export function update(worker: TypingStatusWorker, new_recipient_ids: number[] | null): void {
    if (state !== null) {
        // We need to use _.isEqual for comparisons; === doesn't work
        // on arrays.
        if (_.isEqual(new_recipient_ids, state.current_recipient_ids)) {
            // Nothing has really changed, except we may need
            // to send a ping to the server.
            maybe_ping_server(worker, new_recipient_ids!);

            // We can also extend out our idle time.
            state.idle_timer = start_or_extend_idle_timer(worker);

            return;
        }

        // We apparently stopped talking to our old recipients,
        // so we must stop the old notification.  Don't return
        // yet, because we may have new recipients.
        stop_last_notification(worker);
    }

    if (new_recipient_ids === null) {
        // If we are not talking to somebody we care about,
        // then there is no more action to take.
        return;
    }

    // We just started talking to these recipients, so notify
    // the server.
    state = {
        current_recipient_ids: new_recipient_ids,
        next_send_start_time: 0,
        idle_timer: start_or_extend_idle_timer(worker),
    };
    const current_time = worker.get_current_time();
    actually_ping_server(worker, new_recipient_ids, current_time);
}
