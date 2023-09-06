import $ from "jquery";

import * as blueslip from "./blueslip";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";
import * as poll_widget from "./poll_widget";
import * as todo_widget from "./todo_widget";
import * as zform from "./zform";

const widgets = new Map([
    ["poll", poll_widget],
    ["todo", todo_widget],
    ["zform", zform],
]);

export const widget_contents = new Map();

export function clear_for_testing() {
    widget_contents.clear();
}

function set_widget_in_message($row, $widget_elem) {
    const $content_holder = $row.find(".message_content");

    // Avoid adding the $widget_elem if it already exists.
    // This can happen when the app loads in the "Recent Conversations"
    // view and the user changes the view to "All messages".
    // This is important since jQuery removes all the event handlers
    // on `empty()`ing an element.
    if ($content_holder.find(".widget-content").length === 0) {
        $content_holder.empty().append($widget_elem);
    }
}

export function activate(in_opts) {
    const widget_type = in_opts.widget_type;
    const extra_data = in_opts.extra_data;
    const events = in_opts.events;
    const $row = in_opts.$row;
    const message = in_opts.message;
    const post_to_server = in_opts.post_to_server;

    events.shift();

    if (!widgets.has(widget_type)) {
        if (widget_type === "tictactoe") {
            return; // don't warn for deleted legacy widget
        }
        blueslip.warn("unknown widget_type", widget_type);
        return;
    }

    const callback = function (data) {
        post_to_server({
            msg_type: "widget",
            data,
        });
    };

    if ($row.attr("id").startsWith("zhome") && narrow_state.active()) {
        // Don't place widget in a home message row if we are narrowed
        // to active state
        return;
    }

    let $widget_elem = widget_contents.get(message.id);
    if ($widget_elem) {
        set_widget_in_message($row, $widget_elem);
        return;
    }

    // We depend on our widgets to use templates to build
    // the HTML that will eventually go in this div.
    $widget_elem = $("<div>").addClass("widget-content");

    widgets.get(widget_type).activate({
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

export function set_widgets_for_list() {
    for (const [idx, $widget_elem] of widget_contents) {
        if (message_lists.current.get(idx) !== undefined) {
            const $row = message_lists.current.get_row(idx);
            set_widget_in_message($row, $widget_elem);
        }
    }
}

export function handle_event(widget_event) {
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
