import $ from "jquery";

import type {GenericWidget, PostToServerFunction} from "./generic_widget.ts";
import {create_widget_instance, is_supported_widget_type} from "./generic_widget.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import type {Event} from "./widget_data.ts";
import type {AnyWidgetData} from "./widget_schema.ts";

// These are the arguments that get passed in to us from the
// submessage system, which is essentially the transport layer
// that lets multiple users interact with the same widget and
// broadcasts submessages among the users. The widgets themselves
// don't really need to know the nitty-gritty of the server details,
// but the server basically just stores submessages in the database
// and then sends events to active users when new submessages arrive
// via the standard Zulip events mechanism.
type ActivateArguments = {
    any_data: AnyWidgetData;
    events: Event[];
    $row: JQuery;
    message: Message;
    post_to_server: PostToServerFunction;
};

const generic_widget_map = new Map<number, GenericWidget>();

export function clear_for_testing(): void {
    generic_widget_map.clear();
}

export function set_widget_for_tests(message_id: number, widget: GenericWidget): void {
    generic_widget_map.set(message_id, widget);
}

export function get_message_ids(): number[] {
    return [...generic_widget_map.keys()];
}

function set_widget_in_message($row: JQuery, $widget_elem: JQuery): void {
    const $content_holder = $row.find(".message_content");
    $content_holder.empty().append($widget_elem);
}

export function activate(in_opts: ActivateArguments): void {
    const {any_data, events, $row, message, post_to_server} = in_opts;

    // the callee will log any appropriate warnings here
    if (!is_supported_widget_type(any_data.widget_type)) {
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

    const generic_widget = create_widget_instance({
        post_to_server,
        $widget_elem,
        message,
        any_data,
    });

    if (!is_message_preview) {
        // Don't re-register the original message's widget event
        // handler.
        generic_widget_map.set(message.id, generic_widget);
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
        generic_widget.handle_inbound_events(events);
    }
}

export function handle_event(widget_event: Event & {message_id: number}): void {
    const generic_widget = generic_widget_map.get(widget_event.message_id);

    if (!generic_widget || message_lists.current?.get_row(widget_event.message_id).length === 0) {
        // It is common for submessage events to arrive on
        // messages that we don't yet have in view. We
        // just ignore them completely here.
        return;
    }

    const events = [widget_event];

    generic_widget.handle_inbound_events(events);
}
