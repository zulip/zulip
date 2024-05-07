import $ from "jquery";

import * as blueslip from "./blueslip";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import type {Event, PollWidgetExtraData} from "./poll_widget";

// TODO: This ZFormExtraData type should be moved to web/src/zform.js when it will be migrated
type ZFormExtraData = {
    type: string;
    heading: string;
    choices: {type: string; reply: string; long_name: string; short_name: string}[];
};

// TODO: This TodoWidgetExtraData type should be moved to web/src/todo_widget.js when it will be migrated
type TodoWidgetExtraData = {
    task_list_title?: string;
    tasks?: {task: string; desc: string}[];
};

type WidgetExtraData = PollWidgetExtraData | TodoWidgetExtraData | ZFormExtraData | null;

type WidgetOptions = {
    widget_type: string;
    extra_data: WidgetExtraData;
    events: Event[];
    $row: JQuery;
    message: Message;
    post_to_server: (data: {msg_type: string; data: string}) => void;
};

type WidgetValue = Record<string, unknown> & {
    activate: (data: {
        $elem: JQuery;
        callback: (data: string) => void;
        message: Message;
        extra_data: WidgetExtraData;
    }) => void;
};

export const widgets = new Map<string, WidgetValue>();
export const widget_contents = new Map<number, JQuery>();

export function clear_for_testing(): void {
    widget_contents.clear();
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
        blueslip.warn("unknown widget_type", widget_type);
        return;
    }

    const callback = function (data: string): void {
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

    widgets.get(widget_type)!.activate({
        $elem: $widget_elem,
        callback,
        message,
        extra_data,
    });

    widget_contents.set(message.id, $widget_elem);
    set_widget_in_message($row, $widget_elem);

    // Replay any events that already happened.  (This is common
    // when you narrow to a message after other users have already
    // interacted with it.)
    if (events.length > 0) {
        $widget_elem.handle_events(events);
    }
}

export function handle_event(widget_event: Event & {message_id: number}): void {
    const $widget_elem = widget_contents.get(widget_event.message_id);

    if (!$widget_elem) {
        // It is common for submessage events to arrive on
        // messages that we don't yet have in view. We
        // just ignore them completely here.
        return;
    }

    const events = [widget_event];

    $widget_elem.handle_events(events);
}
