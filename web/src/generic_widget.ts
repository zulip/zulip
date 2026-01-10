import * as blueslip from "./blueslip.ts";
import type {Message} from "./message_store.ts";
import type {PollWidgetOutboundData} from "./poll_data.ts";
import type {TodoWidgetOutboundData} from "./todo_widget.ts";
import type {Event} from "./widget_data.ts";
import type {AnyWidgetData} from "./widget_schema.ts";

type HandleInboundEventsFunction = (events: Event[]) => void;

export type PostToServerFunction = (data: {msg_type: string; data: WidgetOutboundData}) => void;

type WidgetOutboundData = PollWidgetOutboundData | TodoWidgetOutboundData;

// These are poll, todo, and zform implementations.
// They are currently injected into us from another module
// for historical reasons. (as of January 2026)
type WidgetImplementation = {
    activate: (data: {
        $elem: JQuery;
        callback: (data: WidgetOutboundData) => void;
        message: Message;
        any_data: AnyWidgetData;
    }) => HandleInboundEventsFunction;
};

export const widgets = new Map<string, WidgetImplementation>();

export function is_supported_widget_type(widget_type: string): boolean {
    if (widgets.has(widget_type)) {
        return true;
    }

    if (widget_type === "tictactoe") {
        return false; // don't warn for deleted legacy widget
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
    post_to_server: PostToServerFunction;
    $widget_elem: JQuery;
    message: Message;
    any_data: AnyWidgetData;
}): GenericWidget {
    const {post_to_server, $widget_elem, message, any_data} = info;

    // For historical reasons, we don't directly import the
    // modules that handle poll, todo, and zform.
    const widget_implementation = widgets.get(any_data.widget_type)!;

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

    const inbound_events_handler = widget_implementation.activate({
        $elem: $widget_elem,
        callback: post_to_server_callback,
        message,
        any_data,
    });

    return new GenericWidget(inbound_events_handler);
}
