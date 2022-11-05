import $ from "jquery";
import _ from "lodash";

import * as pm_list_data from "./pm_list_data";
import * as pm_list_dom from "./pm_list_dom";
import * as resize from "./resize";
import * as ui from "./ui";
import * as ui_util from "./ui_util";
import * as vdom from "./vdom";

let prior_dom;

// This module manages the "Private messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

let private_messages_collapsed = false;

// The private messages section can be zoomed in to view more messages.
// This keeps track of if we're zoomed in or not.
let zoomed = false;

function get_private_messages_section_header() {
    return $(
        ".private_messages_container #private_messages_section #private_messages_section_header",
    );
}

export function set_count(count) {
    ui_util.update_unread_count_in_dom(get_private_messages_section_header(), count);
}

function close() {
    private_messages_collapsed = true;
    $("#toggle_private_messages_section_icon").removeClass("fa-caret-down");
    $("#toggle_private_messages_section_icon").addClass("fa-caret-right");

    update_private_messages();
}

export function _build_private_messages_list() {
    const conversations = pm_list_data.get_conversations();
    const pm_list_info = pm_list_data.get_list_info(zoomed);
    const conversations_to_be_shown = pm_list_info.conversations_to_be_shown;
    const more_conversations_unread_count = pm_list_info.more_conversations_unread_count;

    const pm_list_nodes = conversations_to_be_shown.map((conversation) =>
        pm_list_dom.keyed_pm_li(conversation),
    );

    const all_conversations_shown = conversations_to_be_shown.length === conversations.length;
    if (!all_conversations_shown) {
        pm_list_nodes.push(
            pm_list_dom.more_private_conversations_li(more_conversations_unread_count),
        );
    }
    const dom_ast = pm_list_dom.pm_ul(pm_list_nodes);
    return dom_ast;
}

function set_dom_to(new_dom) {
    const $container = ui.get_content_element($("#private_messages_list"));

    function replace_content(html) {
        $container.html(html);
    }

    function find() {
        return $container.find("ul");
    }

    vdom.update(replace_content, find, new_dom, prior_dom);
    prior_dom = new_dom;
}

export function update_private_messages() {
    if (private_messages_collapsed) {
        // In the collapsed state, we will still display the current
        // conversation, to preserve the UI invariant that there's
        // always something highlighted in the left sidebar.
        const conversations = pm_list_data.get_conversations();
        const active_conversation = conversations.find((conversation) => conversation.is_active);

        if (active_conversation) {
            const node = [pm_list_dom.keyed_pm_li(active_conversation)];
            const new_dom = pm_list_dom.pm_ul(node);
            set_dom_to(new_dom);
        } else {
            // Otherwise, empty the section.
            $(".pm-list").empty();
            prior_dom = undefined;
        }
    } else {
        const new_dom = _build_private_messages_list();
        set_dom_to(new_dom);
    }
    // Make sure to update the left sidebar heights after updating PMs.
    setTimeout(resize.resize_stream_filters_container, 0);
}

export function expand() {
    private_messages_collapsed = false;
    $("#toggle_private_messages_section_icon").addClass("fa-caret-down");
    $("#toggle_private_messages_section_icon").removeClass("fa-caret-right");
    update_private_messages();
}

export function update_dom_with_unread_counts(counts) {
    // In theory, we could support passing the counts object through
    // to pm_list_data, rather than fetching it directly there. But
    // it's not an important optimization, because it's unlikely a
    // user would have 10,000s of unread PMs where it could matter.
    update_private_messages();
    // This is just the global unread count.
    set_count(counts.private_message_count);
}

export function highlight_all_private_messages_view() {
    $(".private_messages_container").addClass("active_private_messages_section");
}

function unhighlight_all_private_messages_view() {
    $(".private_messages_container").removeClass("active_private_messages_section");
}

export function handle_narrow_activated(filter) {
    const active_filter = filter;
    const is_all_private_message_view = _.isEqual(active_filter.sorted_term_types(), [
        "is-private",
    ]);
    const narrow_to_private_messages_section = active_filter.operands("pm-with").length !== 0;

    if (is_all_private_message_view) {
        highlight_all_private_messages_view();
    } else {
        unhighlight_all_private_messages_view();
    }
    if (narrow_to_private_messages_section) {
        update_private_messages();
    }
}

export function handle_narrow_deactivated() {
    // Since one can renarrow via the keyboard shortcut or similar, we
    // avoid disturbing the zoomed state here.
    unhighlight_all_private_messages_view();
    update_private_messages();
}

export function is_private_messages_collapsed() {
    return private_messages_collapsed;
}

export function toggle_private_messages_section() {
    // change the state of PM section depending on the previous state.
    if (private_messages_collapsed) {
        expand();
    } else {
        close();
    }
}

function zoom_in() {
    zoomed = true;
    update_private_messages();
    $(".private_messages_container").removeClass("zoom-out").addClass("zoom-in");
    $("#streams_list").hide();
    $(".left-sidebar .right-sidebar-items").hide();
}

function zoom_out() {
    zoomed = false;
    update_private_messages();
    $(".private_messages_container").removeClass("zoom-in").addClass("zoom-out");
    $("#streams_list").show();
    $(".left-sidebar .right-sidebar-items").show();
}

export function initialize() {
    $(".private_messages_container").on("click", "#show_more_private_messages", (e) => {
        e.stopPropagation();
        e.preventDefault();

        zoom_in();
    });

    $(".private_messages_container").on("click", "#hide_more_private_messages", (e) => {
        e.stopPropagation();
        e.preventDefault();

        zoom_out();
    });
}
