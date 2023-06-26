import * as Sentry from "@sentry/browser";

import * as blueslip from "./blueslip";
import * as server_events from "./server_events";

export let next_local_id;
export const messages = new Map();

export function reset_id_state() {
    next_local_id = 0;
}

export function get_new_local_id() {
    next_local_id += 1;
    const local_id = next_local_id;
    return "loc-" + local_id.toString();
}

export class MessageState {
    local_id = undefined;
    locally_echoed = undefined;
    rendered_changed = false;

    server_acked = false;
    saw_event = false;

    txn = undefined;
    event_span = undefined;

    constructor(opts) {
        this.local_id = opts.local_id;
        this.locally_echoed = opts.locally_echoed;
    }

    start_send() {
        this.txn = Sentry.startTransaction({
            op: "function",
            description: "message send",
            name: "message send",
        });
        this.event_span = this.txn.startChild({
            op: "function",
            description: "message send (server event loop)",
        });
        return this.txn;
    }

    mark_disparity() {
        this.rendered_changed = true;
    }

    maybe_restart_event_loop() {
        if (this.saw_event) {
            // We got our event, no need to do anything
            return;
        }

        blueslip.log(
            `Restarting get_events due to delayed receipt of sent message ${this.local_id}`,
        );

        server_events.restart_get_events();
    }

    report_server_ack() {
        this.server_acked = true;
        this.maybe_finish_txn();
        // We only start our timer for events coming in here,
        // since it's plausible the server rejected our message,
        // or took a while to process it, but there is nothing
        // wrong with our event loop.

        if (!this.received) {
            setTimeout(() => this.maybe_restart_event_loop(), 5000);
        }
    }

    report_event_received() {
        if (!this.event_span) {
            return;
        }
        this.saw_event = true;
        this.event_span.finish();
        this.maybe_finish_txn();
    }

    maybe_finish_txn() {
        if (!this.saw_event || !this.server_acked) {
            return;
        }
        const setTag = (name, val) => {
            const str_val = val ? "true" : "false";
            this.event_span.setTag(name, str_val);
            this.txn.setTag(name, str_val);
        };
        setTag("rendered_changed", this.rendered_changed);
        setTag("locally_echoed", this.locally_echoed);
        this.txn.finish();
        messages.delete(this.local_id);
    }
}

export function start_tracking_message(opts) {
    const local_id = opts.local_id;

    if (!opts.local_id) {
        blueslip.error("You must supply a local_id");
        return;
    }

    if (messages.has(local_id)) {
        blueslip.error("We are re-using a local_id");
        return;
    }

    const state = new MessageState(opts);

    messages.set(local_id, state);
}

export function get_message_state(local_id) {
    const state = messages.get(local_id);

    if (!state) {
        blueslip.warn("Unknown local_id: " + local_id);
    }

    return state;
}

export function start_send(local_id) {
    const state = get_message_state(local_id);
    if (!state) {
        return undefined;
    }

    return state.start_send();
}

export function report_server_ack(local_id) {
    const state = get_message_state(local_id);
    if (!state) {
        return;
    }

    state.report_server_ack();
}

export function mark_disparity(local_id) {
    const state = get_message_state(local_id);
    if (!state) {
        return;
    }
    state.mark_disparity();
}

export function report_event_received(local_id) {
    if (local_id === undefined) {
        return;
    }
    const state = get_message_state(local_id);
    if (!state) {
        return;
    }

    state.report_event_received();
}

export function initialize() {
    reset_id_state();
}
