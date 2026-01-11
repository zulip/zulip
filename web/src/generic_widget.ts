import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import type {Message} from "./message_store.ts";
import type {PollWidgetOutboundData} from "./poll_data.ts";
import {poll_setup_data_schema} from "./poll_data.ts";
import * as poll_widget from "./poll_widget.ts";
import type {TodoWidgetOutboundData} from "./todo_widget.ts";
import * as todo_widget from "./todo_widget.ts";
import * as zform from "./zform.ts";

// Our Event data from the server is opaque and unknown
// until the widget parses it with zod.
export type Event = {sender_id: number; data: unknown};

type HandleInboundEventsFunction = (events: Event[]) => void;

export type PostToServerFunction = (data: {msg_type: string; data: WidgetOutboundData}) => void;

type WidgetOutboundData = PollWidgetOutboundData | TodoWidgetOutboundData;

export function is_supported_widget_type(widget_type: string): boolean {
    if (widget_type === "poll" || widget_type === "todo" || widget_type === "zform") {
        return true;
    }

    blueslip.warn("unknown widget_type", {widget_type});
    return false;
}

export class GenericWidget {
    // Eventually we will have concrete classes for PollWidget,
    // TodoWidget, and ZformWidget, but for now we need this
    // wrapper class.
    inbound_events_handler: HandleInboundEventsFunction;

    constructor(inbound_events_handler: HandleInboundEventsFunction) {
        this.inbound_events_handler = inbound_events_handler;
    }

    handle_inbound_events(events: Event[]): void {
        this.inbound_events_handler(events);
    }
}

export function create_widget_instance(info: {
    widget_type: string;
    post_to_server: PostToServerFunction;
    $widget_elem: JQuery;
    message: Message;
    extra_data: unknown; // parsed by individual widgets
}): GenericWidget {
    const {widget_type, post_to_server, $widget_elem, message, extra_data} = info;

    // We pass this is into the widgets to provide them a black-box
    // service that sends any events **outbound** to the other active
    // users. For example, if I vote on a poll, the widget from my
    // client will send data to the server using this callback, and
    // then the server will broadcast my poll vote to other users.
    function post_to_server_callback(data: WidgetOutboundData): void {
        post_to_server({
            msg_type: "widget",
            data,
        });
    }

    function get_inbound_event_handler(
        widget_type: string,
    ): HandleInboundEventsFunction | undefined {
        // These activate functions are annoying, and they
        // are showell's fault from 2018. But they will go away soon,
        // or at least better encapsulated.
        // (showell wrote this comment)
        switch (widget_type) {
            case "poll": {
                const poll_setup_data = poll_setup_data_schema.parse(extra_data);
                return poll_widget.activate({
                    $elem: $widget_elem,
                    callback: post_to_server_callback,
                    message,
                    setup_data: poll_setup_data,
                });
            }
            case "todo": {
                return todo_widget.activate({
                    $elem: $widget_elem,
                    callback: post_to_server_callback,
                    message,
                    extra_data,
                });
            }
            case "zform": {
                return zform.activate({
                    $elem: $widget_elem,
                    message,
                    extra_data,
                });
            }
        }

        // We should never reach here, because upstream
        // code will validate widget_type.
        assert(false);
        return undefined;
    }

    const inbound_events_handler = get_inbound_event_handler(widget_type);
    assert(inbound_events_handler !== undefined);

    return new GenericWidget(inbound_events_handler);
}
