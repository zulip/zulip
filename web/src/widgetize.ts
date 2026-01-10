import $ from "jquery";

import type {GenericWidget, PostToServerFunction} from "./generic_widget.ts";
import {create_widget_instance, is_supported_widget_type} from "./generic_widget.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";

// Our Event data from the server is opaque and unknown
// until the widget parses it with zod.
export type Event = {sender_id: number; data: unknown};

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
    extra_data: unknown; // parsed by each widget
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

    // Finally create our widget!  Note that at this layer, the
    // "extra_data" object is still completely opaque and
    // unvalidated. Each individual widget parses the data
    // according to the shape it expects. To give a concrete
    // example, the todo widget expects extra_data to include
    // something like a "task_list_title" field, and that
    // field would make no sense to either the poll or zform
    // widget.
    const generic_widget = create_widget_instance({
        widget_type,
        post_to_server,
        $widget_elem,
        message,
        extra_data,
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
