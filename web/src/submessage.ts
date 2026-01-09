import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as ephemeral_widget from "./ephemeral_widget.ts";
import type {MessageList} from "./message_list.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import {widget_data_schema} from "./widget_schema.ts";
import type {WidgetOutboundData} from "./widget_schema.ts";
import * as widgetize from "./widgetize.ts";

export type Submessage = z.infer<typeof message_store.submessage_schema>;

const widget_data_event_schema = z.object({
    sender_id: z.number(),
    data: widget_data_schema,
});

const inbound_data_event_schema = z.object({
    sender_id: z.number(),
    data: z.intersection(
        z.object({
            // type is optional for backwards compatibility with older submessages
            type: z.optional(z.string()),
        }),
        z.record(z.string(), z.unknown()),
    ),
});

const submessages_event_schema = z.tuple([widget_data_event_schema], inbound_data_event_schema);

type SubmessageEvents = z.infer<typeof submessages_event_schema>;

export function get_message_events(message: Message): SubmessageEvents | undefined {
    if (message.locally_echoed) {
        return undefined;
    }

    if (message.submessages.length === 0) {
        return undefined;
    }

    message.submessages.sort((m1, m2) => m1.id - m2.id);

    const events = message.submessages.map((obj): {sender_id: number; data: unknown} => ({
        sender_id: obj.sender_id,
        data: JSON.parse(obj.content),
    }));
    const clean_events = submessages_event_schema.parse(events);
    return clean_events;
}

export function process_widget_rows_in_list(list: MessageList | undefined): void {
    for (const message_id of widgetize.widget_event_handlers.keys()) {
        const $row = list?.get_row(message_id);
        if ($row && $row.length > 0) {
            process_submessages({message_id, $row});
        }
    }
}

export function process_submessages(in_opts: {$row: JQuery; message_id: number}): void {
    // This happens in our rendering path, so we try to limit any
    // damage that may be triggered by one rogue message.
    try {
        do_process_submessages(in_opts);
        return;
    } catch (error) {
        blueslip.error("Failed to do_process_submessages", undefined, error);
        return;
    }
}

export function do_process_submessages(in_opts: {$row: JQuery; message_id: number}): void {
    const message_id = in_opts.message_id;
    const message = message_store.get(message_id);

    if (!message) {
        return;
    }

    const $row = in_opts.$row;

    // Render any ephemeral responses (these are separate from main widgets)
    ephemeral_widget.render_ephemeral_responses($row, message);

    const events = get_message_events(message);

    if (!events) {
        return;
    }
    const [widget_event, ...inbound_events] = events;

    if (widget_event.sender_id !== message.sender_id) {
        blueslip.warn(`User ${widget_event.sender_id} tried to hijack message ${message.id}`);
        return;
    }

    // Right now, our only use of submessages is widgets.

    const data = widget_event.data;

    if (data === undefined) {
        return;
    }

    const widget_type = data.widget_type;

    if (widget_type === undefined) {
        return;
    }

    const post_to_server = make_server_callback(message_id);

    widgetize.activate({
        widget_type,
        extra_data: data.extra_data,
        events: inbound_events,
        $row,
        message,
        post_to_server,
    });
}

export function update_message(submsg: Submessage): void {
    const message = message_store.get(submsg.message_id);

    if (message === undefined) {
        // This is generally not a problem--the server
        // can send us events without us having received
        // the original message, since the server doesn't
        // track that.
        return;
    }

    const existing = message.submessages.find((sm) => sm.id === submsg.id);

    if (existing !== undefined) {
        blueslip.warn("Got submessage multiple times: " + submsg.id);
        return;
    }

    message.submessages.push(submsg);
}

export function handle_remove_event(message_id: number, submessage_id: number): void {
    const message = message_store.get(message_id);
    if (!message) {
        return;
    }

    // Remove the submessage from the message's submessages array
    const index = message.submessages.findIndex((sm) => sm.id === submessage_id);
    if (index !== -1) {
        message.submessages.splice(index, 1);
    }

    // Re-render ephemeral responses for this message
    const $row = message_lists.current?.get_row(message_id);
    if ($row && $row.length > 0) {
        ephemeral_widget.render_ephemeral_responses($row, message);
    }
}

export function handle_event(submsg: Submessage): void {
    // Update message.submessages in case we haven't actually
    // activated the widget yet, so that when the message does
    // come in view, the data will be complete.
    update_message(submsg);

    // Check if this is an ephemeral response - render it immediately
    if (ephemeral_widget.is_ephemeral_submessage(submsg)) {
        const message = message_store.get(submsg.message_id);
        if (message) {
            const $row = message_lists.current?.get_row(submsg.message_id);
            if ($row && $row.length > 0) {
                ephemeral_widget.render_ephemeral_responses($row, message);
            }
        }
        return;
    }

    // Right now, our only use of submessages is widgets.
    const msg_type = submsg.msg_type;

    if (msg_type !== "widget") {
        blueslip.warn("unknown msg_type: " + msg_type);
        return;
    }

    let data: unknown;

    try {
        data = JSON.parse(submsg.content);
    } catch {
        blueslip.warn("server sent us invalid json in handle_event: " + submsg.content);
        return;
    }

    widgetize.handle_event({
        sender_id: submsg.sender_id,
        message_id: submsg.message_id,
        data,
    });
}

export function make_server_callback(
    message_id: number,
): (opts: {msg_type: string; data: WidgetOutboundData}) => void {
    return function (opts: {msg_type: string; data: WidgetOutboundData}) {
        const url = "/json/submessage";

        void channel.post({
            url,
            data: {
                message_id,
                msg_type: opts.msg_type,
                content: JSON.stringify(opts.data),
            },
        });
    };
}
