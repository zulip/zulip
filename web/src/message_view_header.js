import $ from "jquery";

import render_message_view_header from "../templates/message_view_header.hbs";

import {$t} from "./i18n";
import * as inbox_util from "./inbox_util";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import * as recent_view_util from "./recent_view_util";
import * as rendered_markdown from "./rendered_markdown";
import * as search from "./search";

function make_message_view_header(filter) {
    const message_view_header = {};
    if (recent_view_util.is_visible()) {
        return {
            title: $t({defaultMessage: "Recent conversations"}),
            zulip_icon: "clock",
        };
    }
    if (inbox_util.is_visible()) {
        return {
            title: $t({defaultMessage: "Inbox"}),
            zulip_icon: "inbox",
        };
    }
    if (filter === undefined) {
        return {
            title: $t({defaultMessage: "All messages"}),
            zulip_icon: "all-messages",
        };
    }
    message_view_header.title = filter.get_title();
    message_view_header.is_spectator = page_params.is_spectator;
    filter.add_icon_data(message_view_header);
    if (filter.has_operator("stream") && !filter._sub) {
        message_view_header.sub_count = "0";
        message_view_header.formatted_sub_count = "0";
        message_view_header.rendered_narrow_description = $t({
            defaultMessage: "This stream does not exist or is private.",
        });
        return message_view_header;
    }
    if (filter._sub) {
        // We can now be certain that the narrow
        // involves a stream which exists and
        // the current user can access.
        const current_stream = filter._sub;
        message_view_header.rendered_narrow_description = current_stream.rendered_description;
        const sub_count = peer_data.get_subscriber_count(current_stream.stream_id);
        message_view_header.sub_count = sub_count;
        message_view_header.stream = current_stream;
        message_view_header.stream_settings_link =
            "#streams/" + current_stream.stream_id + "/" + current_stream.name;
    }
    return message_view_header;
}

export function colorize_message_view_header() {
    const filter = narrow_state.filter();
    if (filter === undefined || !filter._sub) {
        return;
    }
    // selecting i instead of .fa because web public streams have custom icon.
    $("#message_view_header a.stream i").css("color", filter._sub.color);
}

function append_and_display_title_area(message_view_header_data) {
    const $message_view_header_elem = $("#message_view_header");
    $message_view_header_elem.empty();
    const rendered = render_message_view_header(message_view_header_data);
    $message_view_header_elem.append(rendered);
    if (message_view_header_data.stream_settings_link) {
        colorize_message_view_header();
    }
    $message_view_header_elem.removeClass("notdisplayed");
    const $content = $message_view_header_elem.find("span.rendered_markdown");
    if ($content) {
        // Update syntax like stream names, emojis, mentions, timestamps.
        rendered_markdown.update_elements($content);
    }
}

function build_message_view_header(filter) {
    // This makes sure we don't waste time appending
    // message_view_header on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        search.open_search_bar_and_close_narrow_description();
        $("#search_query").val(narrow_state.search_string());
    } else {
        const message_view_header_data = make_message_view_header(filter);
        append_and_display_title_area(message_view_header_data);
        search.close_search_bar_and_open_narrow_description();
    }
}

export function initialize() {
    render_title_area();
}

export function render_title_area() {
    const filter = narrow_state.filter();
    build_message_view_header(filter);
}

// This function checks if "modified_sub" which is the stream whose values
// have been updated is the same as the stream which is currently
// narrowed (filter._sub) and rerenders if necessary
export function maybe_rerender_title_area_for_stream(modified_sub) {
    const filter = narrow_state.filter();
    if (filter && filter._sub && filter._sub.stream_id === modified_sub.stream_id) {
        render_title_area();
    }
}
