import $ from "jquery";

import * as blueslip from "./blueslip.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import type {PollWidgetExtraData, PollWidgetOutboundData} from "./poll_data.ts";
import type {TodoWidgetExtraData, TodoWidgetOutboundData} from "./todo_widget.ts";
import type {Event} from "./widget_data.ts";
import type {ZFormExtraData} from "./zform_data.ts";

export type WidgetExtraData = PollWidgetExtraData | TodoWidgetExtraData | ZFormExtraData | null;

type WidgetOutboundData = PollWidgetOutboundData | TodoWidgetOutboundData;

type PostToServerFunction = (data: {msg_type: string; data: WidgetOutboundData}) => void;
type HandleInboundEventsFunction = (events: Event[]) => void;

// These are the arguments that get passed in to us from the
// submessage system, which is essentially the transport layer
// that lets multiple users interact with the same widget and
// broadcasts submessages among the users. The widgets themselves
// don't really need to know the nitty-gritty of the server details,
// but the server basically just stores submessages in the database
// and then sends events to active users when new submessages arrive
// via the standard Zulip events mechanism.
type ActivateArguments = {
    widget_type: string;
    extra_data: WidgetExtraData;
    events: Event[];
    $row: JQuery;
    message: Message;
    post_to_server: PostToServerFunction;
};

// These are poll, todo, and zform implementations.
// They are currently injected into us from another module
// for historical reasons. (as of January 2026)
type WidgetImplementation = Record<string, unknown> & {
    activate: (data: {
        $elem: JQuery;
        callback: (data: WidgetOutboundData) => void;
        message: Message;
        extra_data: WidgetExtraData;
    }) => HandleInboundEventsFunction;
};

export const widgets = new Map<string, WidgetImplementation>();
export const widget_event_handlers = new Map<number, (events: Event[]) => void>();

export function clear_for_testing(): void {
    widget_event_handlers.clear();
}

function set_widget_in_message($row: JQuery, $widget_elem: JQuery): void {
    const $content_holder = $row.find(".message_content");
    $content_holder.empty().append($widget_elem);
}

function is_supported_widget_type(widget_type: string): boolean {
    if (widgets.has(widget_type)) {
        return true;
    }

    if (widget_type === "tictactoe") {
        return false; // don't warn for deleted legacy widget
    }

    blueslip.warn("unknown widget_type", {widget_type});
    return false;
}

function create_widget_instance(info: {
    widget_type: string;
    post_to_server: PostToServerFunction;
    $widget_elem: JQuery;
    message: Message;
    extra_data: WidgetExtraData;
}): HandleInboundEventsFunction {
    const {widget_type, post_to_server, $widget_elem, message, extra_data} = info;

    // For historical reasons, we don't directly import the
    // modules that handle poll, todo, and zform.
    const widget_implementation = widgets.get(widget_type)!;

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

    const event_handler = widget_implementation.activate({
        $elem: $widget_elem,
        callback: post_to_server_callback,
        message,
        extra_data,
    });

    // Our widget objects are not yet built from JS/TS classes.
    // They look to the outside world as a simple event handler
    // function. This should change soon.
    return event_handler;
}

export function activate(in_opts: ActivateArguments): void {
    const widget_type = in_opts.widget_type;
    const extra_data = in_opts.extra_data;
    const events = in_opts.events;
    const $row = in_opts.$row;
    const message = in_opts.message;
    const post_to_server = in_opts.post_to_server;

    // the callee will log any appropriate warnings here
    if (!is_supported_widget_type(widget_type)) {
        return;
    }

    const is_message_preview = $row.parent()?.attr("id") === "report-message-preview-container";

    if (
        !$row.attr("id")!.startsWith(`message-row-${message_lists.current?.id}-`) &&
        !is_message_preview
    ) {
        // Don't activate widgets for messages that are not in the current view or
        // in message report modal.
        return;
    }

    // We depend on our widget implementations to build the
    // DOM and event handlers that eventually go in this div.
    const $widget_elem = $("<div>").addClass("widget-content");

    const event_handler = create_widget_instance({
        widget_type,
        post_to_server,
        $widget_elem,
        message,
        extra_data,
    });

    if (!is_message_preview) {
        // Don't re-register the original message's widget event
        // handler.
        widget_event_handlers.set(message.id, event_handler);
    }

    set_widget_in_message($row, $widget_elem);

    // Replay any events that already happened.  (This is common
    // when the user opens a conversation with a poll that
    // other users have already interacted with.)
    //
    // If there are no events to replay, don't annoy the widget
    // by making it handle the degenerate case. In most cases
    // it would just lead to an extra re-render or something
    // harmless, but there's still no point.
    if (events.length > 0) {
        event_handler(events);
    }
}

export function handle_event(widget_event: Event & {message_id: number}): void {
    const event_handler = widget_event_handlers.get(widget_event.message_id);

    if (!event_handler || message_lists.current?.get_row(widget_event.message_id).length === 0) {
        // It is common for submessage events to arrive on
        // messages that we don't yet have in view. We
        // just ignore them completely here.
        return;
    }

    const events = [widget_event];

    event_handler(events);
}
