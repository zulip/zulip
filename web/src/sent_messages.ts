import * as Sentry from "@sentry/browser";

import * as blueslip from "./blueslip.ts";

export let next_local_id = 0;
export const messages = new Map<string, MessageState>();

export function get_new_local_id(): string {
    next_local_id += 1;
    const local_id = next_local_id;
    return "loc-" + local_id.toString();
}

export class MessageState {
    local_id: string;
    locally_echoed: boolean;
    rendered_changed = false;

    server_acked = false;
    saw_event = false;

    span: Sentry.Span | undefined = undefined;
    event_span: Sentry.Span | undefined = undefined;

    constructor(opts: {local_id: string; locally_echoed: boolean}) {
        this.local_id = opts.local_id;
        this.locally_echoed = opts.locally_echoed;
    }

    wrap_send(callback: () => void): void {
        Sentry.startSpanManual(
            {
                op: "function",
                name: "message send",
            },
            (span) => {
                try {
                    this.span = span;
                    this.event_span = Sentry.startInactiveSpan({
                        op: "function",
                        name: "message send (server event loop)",
                    });
                    callback();
                } catch (error) {
                    this.event_span?.end();
                    span?.end();
                    throw error;
                }
            },
        );
    }

    mark_disparity(): void {
        this.rendered_changed = true;
    }

    report_server_ack(): void {
        this.server_acked = true;
        this.maybe_finish_txn();
    }

    report_event_received(): void {
        if (!this.event_span) {
            return;
        }
        this.saw_event = true;
        this.event_span?.end();
        this.maybe_finish_txn();
    }

    report_error(): void {
        this.event_span?.end();
        this.span?.end();
    }

    maybe_finish_txn(): void {
        if (!this.saw_event || !this.server_acked) {
            return;
        }
        const setTag = (name: string, val: boolean): void => {
            const str_val = val ? "true" : "false";
            this.event_span?.setAttribute(name, str_val);
            this.span?.setAttribute(name, str_val);
        };
        setTag("rendered_changed", this.rendered_changed);
        setTag("locally_echoed", this.locally_echoed);
        this.span?.end();
        messages.delete(this.local_id);
    }
}

export function start_tracking_message(opts: {local_id: string; locally_echoed: boolean}): void {
    const local_id = opts.local_id;

    if (!opts.local_id) {
        blueslip.error("You must supply a local_id");
        return;
    }

    if (messages.has(local_id)) {
        blueslip.error("We are reusing a local_id");
        return;
    }

    const state = new MessageState(opts);

    messages.set(local_id, state);
}

export function get_message_state(local_id: string): MessageState | undefined {
    const state = messages.get(local_id);

    if (!state) {
        blueslip.warn("Unknown local_id: " + local_id);
    }

    return state;
}

export function wrap_send(local_id: string, callback: () => void): void {
    const state = get_message_state(local_id);
    if (state) {
        state.wrap_send(callback);
    } else {
        callback();
    }
}

export function mark_disparity(local_id: string): void {
    const state = get_message_state(local_id);
    if (!state) {
        return;
    }
    state.mark_disparity();
}

export function report_event_received(local_id: string): void {
    if (local_id === undefined) {
        return;
    }
    const state = get_message_state(local_id);
    if (!state) {
        return;
    }

    state.report_event_received();
}
