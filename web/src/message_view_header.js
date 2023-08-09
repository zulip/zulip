import $ from "jquery";

import render_message_view_header from "../templates/message_view_header.hbs";

import {$t} from "./i18n";
import * as inbox_util from "./inbox_util";
import * as narrow_state from "./narrow_state";
import * as peer_data from "./peer_data";
import * as popovers from "./popovers";
import * as recent_view_util from "./recent_view_util";
import * as rendered_markdown from "./rendered_markdown";
import * as search from "./search";

function get_formatted_sub_count(sub_count) {
    if (sub_count >= 1000) {
        // parseInt() is used to floor the value of division to an integer
        sub_count = Number.parseInt(sub_count / 1000, 10) + "k";
    }
    return sub_count;
}

function make_message_view_header(filter) {
    const message_view_header = {};
    if (recent_view_util.is_visible()) {
        return {
            title: $t({defaultMessage: "Recent conversations"}),
            icon: "clock-o",
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
            icon: "align-left",
        };
    }
    message_view_header.title = filter.get_title();
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
        message_view_header.formatted_sub_count = get_formatted_sub_count(sub_count);
        // the "title" is passed as a variable and doesn't get translated (nor should it)
        message_view_header.sub_count_tooltip_text = $t(
            {defaultMessage: "This stream has {count} subscribers."},
            {count: message_view_header.sub_count},
        );
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

function bind_title_area_handlers() {
    $(".search_closed").on("click", (e) => {
        popovers.hide_all();
        search.initiate_search();
        e.preventDefault();
        e.stopPropagation();
    });

    $("#message_view_header .navbar-click-opens-search").on("click", (e) => {
        popovers.hide_all();

        if (document.getSelection().type === "Range") {
            // Allow copy/paste to work normally without interference.
            return;
        }

        // Let links behave normally, ie, do nothing if <a>
        if ($(e.target).closest("a").length === 0) {
            search.initiate_search();
            e.preventDefault();
            e.stopPropagation();
        }
    });

    // handler that makes sure that hover plays nicely
    // with whether search is being opened or not.
    $("#message_view_header .narrow_description > a")
        .on("mouseenter", () => {
            $("#message_view_header .search_closed").css("opacity", 0.5);
        })
        .on("mouseleave", () => {
            $("#message_view_header .search_closed").css("opacity", "");
        });
}

function build_message_view_header(filter) {
    // This makes sure we don't waste time appending
    // message_view_header on a template where it's never used
    if (filter && !filter.is_common_narrow()) {
        open_search_bar_and_close_narrow_description();
    } else {
        const message_view_header_data = make_message_view_header(filter);
        append_and_display_title_area(message_view_header_data);
        bind_title_area_handlers();
        close_search_bar_and_open_narrow_description();
    }
}

// we rely entirely on this function to ensure
// the searchbar has the right text.
export function reset_searchbox_text() {
    let search_string = narrow_state.search_string();
    if (search_string !== "") {
        if (!narrow_state.filter().is_search()) {
            // saves the user a keystroke for quick searches
            search_string = search_string + " ";
        }
        $("#search_query").val(search_string);
    }
}

export function exit_search() {
    const filter = narrow_state.filter();
    if (!filter || filter.is_common_narrow()) {
        // for common narrows, we change the UI (and don't redirect)
        close_search_bar_and_open_narrow_description();
    } else {
        // for "searching narrows", we redirect
        window.location.href = filter.generate_redirect_url();
    }
    $(".app").trigger("focus");
}

export function initialize() {
    render_title_area();

    // register searchbar click handler
    $("#search_exit").on("click", (e) => {
        popovers.hide_all();
        exit_search();
        e.preventDefault();
        e.stopPropagation();
    });
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

export function open_search_bar_and_close_narrow_description() {
    reset_searchbox_text();
    $(".navbar-search").addClass("expanded");
    $("#message_view_header").addClass("hidden");
}

export function close_search_bar_and_open_narrow_description() {
    const filter = narrow_state.filter();
    if (!filter || filter.is_common_narrow()) {
        $(".navbar-search").removeClass("expanded");
        $("#message_view_header").removeClass("hidden");
    }
}
