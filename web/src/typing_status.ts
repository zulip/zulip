import _ from "lodash";
import assert from "minimalistic-assert";

type StreamTopic = {
    stream_id: number;
    topic: string;
};
export type Recipient =
    | {
          message_type: "direct";
          notification_event_type: "typing";
          ids: number[];
      }
    | (StreamTopic & {
          message_type: "stream";
          notification_event_type: "typing";
      })
    | {
          notification_event_type: "typing_message_edit";
          message_id: number;
      };

type TypingStatusWorker = {
    get_current_time: () => number;
    notify_server_start: (recipient: Recipient) => void;
    notify_server_stop: (recipient: Recipient) => void;
};

export type EditingStatusWorker = {
    get_current_time: () => number;
    notify_server_editing_start: (recipient: Recipient) => void;
    notify_server_editing_stop: (recipient: Recipient) => void;
};

type TypingStatusState = {
    current_recipient: Recipient;
    next_send_start_time: number;
    idle_timer: ReturnType<typeof setTimeout>;
};

function lower_same(a: string, b: string): boolean {
    return a.toLowerCase() === b.toLowerCase();
}

function same_stream_and_topic(a: StreamTopic, b: StreamTopic): boolean {
    // Streams and topics are case-insensitive.
    return a.stream_id === b.stream_id && lower_same(a.topic, b.topic);
}

function same_recipient(a: Recipient | null, b: Recipient | null): boolean {
    if (a === null || b === null) {
        return false;
    }

    if (a.notification_event_type === "typing" && b.notification_event_type === "typing") {
        if (a.message_type === "direct" && b.message_type === "direct") {
            // direct message recipients
            return _.isEqual(a.ids, b.ids);
        } else if (a.message_type === "stream" && b.message_type === "stream") {
            // stream recipients
            return same_stream_and_topic(a, b);
        }
    }
    return false;
}

/** Exported only for tests. */
export let state: TypingStatusState | null = null;
export const editing_state = new Map<number, TypingStatusState>();

export function rewire_state(value: typeof state): void {
    state = value;
}

/** Exported only for tests. */
export let stop_last_notification = (worker: TypingStatusWorker): void => {
    assert(state !== null, "State object should not be null here.");
    clearTimeout(state.idle_timer);
    worker.notify_server_stop(state.current_recipient);
    state = null;
};

export function stop_notification_for_message_edit(
    worker: EditingStatusWorker,
    message_id: number,
): void {
    const state = editing_state.get(message_id);
    if (state !== undefined) {
        clearTimeout(state.idle_timer);
        worker.notify_server_editing_stop(state.current_recipient);
        editing_state.delete(message_id);
    }
}

export function rewire_stop_last_notification(value: typeof stop_last_notification): void {
    stop_last_notification = value;
}

/** Exported only for tests. */
export let start_or_extend_idle_timer = (
    worker: TypingStatusWorker,
    typing_stopped_wait_period: number,
): ReturnType<typeof setTimeout> => {
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
    return setTimeout(on_idle_timeout, typing_stopped_wait_period);
};

function start_or_extend_idle_timer_for_message_edit(
    worker: EditingStatusWorker,
    message_id: number,
    typing_stopped_wait_period: number,
): ReturnType<typeof setTimeout> {
    function on_idle_timeout(): void {
        // We don't do any real error checking here, because
        // if we've been idle, we need to tell folks, and if
        // our current recipients has changed, previous code will
        // have stopped the timer.
        stop_notification_for_message_edit(worker, message_id);
    }
    const state = editing_state.get(message_id);
    if (state?.idle_timer) {
        clearTimeout(state.idle_timer);
    }

    return setTimeout(on_idle_timeout, typing_stopped_wait_period);
}

export function rewire_start_or_extend_idle_timer(value: typeof start_or_extend_idle_timer): void {
    start_or_extend_idle_timer = value;
}

function set_next_start_time(current_time: number, typing_started_wait_period: number): void {
    assert(state !== null, "State object should not be null here.");
    state.next_send_start_time = current_time + typing_started_wait_period;
}

function set_next_start_time_for_message_edit(
    current_time: number,
    typing_started_wait_period: number,
    message_id: number,
): void {
    const state = editing_state.get(message_id);
    assert(state !== undefined);
    state.next_send_start_time = current_time + typing_started_wait_period;
    editing_state.set(message_id, state);
}

// Exported for tests
export let actually_ping_server = (
    worker: TypingStatusWorker,
    recipient: Recipient,
    current_time: number,
    typing_started_wait_period: number,
): void => {
    worker.notify_server_start(recipient);
    set_next_start_time(current_time, typing_started_wait_period);
};

function actually_ping_server_for_message_edit(
    worker: EditingStatusWorker,
    recipient: Recipient,
    current_time: number,
    typing_started_wait_period: number,
): void {
    assert(recipient.notification_event_type === "typing_message_edit");
    worker.notify_server_editing_start(recipient);
    set_next_start_time_for_message_edit(
        current_time,
        typing_started_wait_period,
        recipient.message_id,
    );
}

export function rewire_actually_ping_server(value: typeof actually_ping_server): void {
    actually_ping_server = value;
}

/** Exported only for tests. */
export let maybe_ping_server = (
    worker: TypingStatusWorker,
    recipient: Recipient,
    typing_started_wait_period: number,
): void => {
    assert(state !== null, "State object should not be null here.");
    const current_time = worker.get_current_time();
    if (current_time > state.next_send_start_time) {
        actually_ping_server(worker, recipient, current_time, typing_started_wait_period);
    }
};

export function maybe_ping_server_for_message_edit(
    worker: EditingStatusWorker,
    recipient: Recipient,
    typing_started_wait_period: number,
): void {
    assert(recipient.notification_event_type === "typing_message_edit");
    const state = editing_state.get(recipient.message_id);
    assert(state !== undefined);
    const current_time = worker.get_current_time();
    if (current_time > state.next_send_start_time) {
        actually_ping_server_for_message_edit(
            worker,
            recipient,
            current_time,
            typing_started_wait_period,
        );
    }
}
export function rewire_maybe_ping_server(value: typeof maybe_ping_server): void {
    maybe_ping_server = value;
}

/**
 * Update our state machine, and the server as needed, on the user's typing status.
 *
 * This can and should be called frequently, on each keystroke.  The
 * implementation sends "still typing" notices at an appropriate throttled
 * rate, and keeps a timer to send a "stopped typing" notice when the user
 * hasn't typed for a few seconds.
 *
 * Call with `new_recipient` as `null` when the user actively stops
 * composing a message.  If the user switches from one set of recipients to
 * another, there's no need to call with `null` in between; the
 * implementation tracks the change and behaves appropriately.
 *
 * See docs/subsystems/typing-indicators.md for detailed background on the
 * typing indicators system.
 *
 * @param {*} worker Callbacks for reaching the real world. See typing.ts
 *   for implementations.
 * @param {*} new_recipient Depends on type of message being composed. If
 *   * Direct message: An Object containing id of users the DM being composed is addressed to
 *    and a message_type="direct" property.
 *   * Stream message: An Object containing stream_id, topic and message_type="stream".
 *   * No message is being composed: `null`
 */
export function update(
    worker: TypingStatusWorker,
    new_recipient: Recipient | null,
    typing_started_wait_period: number,
    typing_stopped_wait_period: number,
): void {
    if (state !== null) {
        if (same_recipient(new_recipient, state.current_recipient)) {
            // Nothing has really changed, except we may need
            // to send a ping to the server.
            maybe_ping_server(worker, new_recipient!, typing_started_wait_period);

            // We can also extend out our idle time.
            state.idle_timer = start_or_extend_idle_timer(worker, typing_stopped_wait_period);

            return;
        }

        // We apparently stopped talking to our old recipients,
        // so we must stop the old notification.  Don't return
        // yet, because we may have new recipients.
        stop_last_notification(worker);
    }

    if (new_recipient === null) {
        // If we are not talking to somebody we care about,
        // then there is no more action to take.
        return;
    }

    // We just started talking to these recipients, so notify
    // the server.
    state = {
        current_recipient: new_recipient,
        next_send_start_time: 0,
        idle_timer: start_or_extend_idle_timer(worker, typing_stopped_wait_period),
    };
    const current_time = worker.get_current_time();
    actually_ping_server(worker, new_recipient, current_time, typing_started_wait_period);
}

export function update_editing_status(
    edit_box_worker: EditingStatusWorker,
    new_recipient: Recipient,
    new_status: "start" | "stop",
    typing_started_wait_period: number,
    typing_stopped_wait_period: number,
): void {
    assert(new_recipient.notification_event_type === "typing_message_edit");
    const message_id = new_recipient.message_id;

    if (new_status === "stop") {
        stop_notification_for_message_edit(edit_box_worker, message_id);
        return;
    }

    if (editing_state.has(message_id)) {
        // Nothing has really changed, except we may need to extend out our idle time.
        const state = editing_state.get(message_id)!;
        state.idle_timer = start_or_extend_idle_timer_for_message_edit(
            edit_box_worker,
            message_id,
            typing_stopped_wait_period,
        );

        // We may need to send a ping to the server too.
        maybe_ping_server_for_message_edit(
            edit_box_worker,
            new_recipient,
            typing_started_wait_period,
        );
        return;
    }

    const edit_state: TypingStatusState = {
        current_recipient: new_recipient,
        next_send_start_time: 0,
        idle_timer: start_or_extend_idle_timer_for_message_edit(
            edit_box_worker,
            message_id,
            typing_stopped_wait_period,
        ),
    };

    editing_state.set(message_id, edit_state);
    const current_time = edit_box_worker.get_current_time();
    actually_ping_server_for_message_edit(
        edit_box_worker,
        new_recipient,
        current_time,
        typing_started_wait_period,
    );
}
