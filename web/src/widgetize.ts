import $ from "jquery";

import * as blueslip from "./blueslip.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import type {Event, PollWidgetExtraData, PollWidgetOutboundData} from "./poll_widget.ts";
import type {TodoWidgetOutboundData} from "./todo_widget.ts";

// TODO: This ZFormExtraData type should be moved to web/src/zform.js when it will be migrated
type ZFormExtraData = {
    type: string;
    heading: string;
    choices: {type: string; reply: string; long_name: string; short_name: string}[];
};

// TODO: This TodoWidgetExtraData type should be moved to web/src/todo_widget.js when it will be migrated
type TodoWidgetExtraData = {
    task_list_title?: string | undefined;
    tasks?: {task: string; desc: string}[] | undefined;
};

type WidgetExtraData = PollWidgetExtraData | TodoWidgetExtraData | ZFormExtraData | null;

type WidgetOptions = {
    widget_type: string;
    extra_data: WidgetExtraData;
    events: Event[];
    $row: JQuery;
    message: Message;
    post_to_server: (data: {
        msg_type: string;
        data: string | PollWidgetOutboundData | TodoWidgetOutboundData;
    }) => void;
};

type WidgetValue = Record<string, unknown> & {
    activate: (data: {
        $elem: JQuery;
        callback: (data: string | PollWidgetOutboundData | TodoWidgetOutboundData) => void;
        message: Message;
        extra_data: WidgetExtraData;
    }) => (events: Event[]) => void;
};

export const widgets = new Map<string, WidgetValue>();
export const widget_event_handlers = new Map<number, (events: Event[]) => void>();

export function clear_for_testing(): void {
    widget_event_handlers.clear();
}

function set_widget_in_message($row: JQuery, $widget_elem: JQuery): void {
    const $content_holder = $row.find(".message_content");
    $content_holder.empty().append($widget_elem);
}

export function activate(in_opts: WidgetOptions): void {
    const widget_type = in_opts.widget_type;
    const extra_data = in_opts.extra_data;
    const events = in_opts.events;
    const $row = in_opts.$row;
    const message = in_opts.message;
    const post_to_server = in_opts.post_to_server;

    if (!widgets.has(widget_type)) {
        if (widget_type === "tictactoe") {
            return; // don't warn for deleted legacy widget
        }
        blueslip.warn("unknown widget_type", {widget_type});
        return;
    }

    const callback = function (
        data: string | PollWidgetOutboundData | TodoWidgetOutboundData,
    ): void {
        post_to_server({
            msg_type: "widget",
            data,
        });
    };

    if (!$row.attr("id")!.startsWith(`message-row-${message_lists.current?.id}-`)) {
        // Don't activate widgets for messages that are not in the current view.
        return;
    }

    // We depend on our widgets to use templates to build
    // the HTML that will eventually go in this div.
    const $widget_elem = $("<div>").addClass("widget-content");

    const event_handler = widgets.get(widget_type)!.activate({
        $elem: $widget_elem,
        callback,
        message,
        extra_data,
    });

    widget_event_handlers.set(message.id, event_handler);
    set_widget_in_message($row, $widget_elem);

    // Replay any events that already happened.  (This is common
    // when you narrow to a message after other users have already
    // interacted with it.)
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
