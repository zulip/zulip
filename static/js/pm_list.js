import $ from "jquery";

import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as pm_list_data from "./pm_list_data";
import * as pm_list_dom from "./pm_list_dom";
import * as stream_popover from "./stream_popover";
import * as ui from "./ui";
import * as ui_util from "./ui_util";
import * as vdom from "./vdom";

let prior_dom;
let private_messages_open = false;

// This module manages the "Private messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

function get_filter_li() {
    return $(".top_left_private_messages .private_messages_header");
}

function set_count(count) {
    ui_util.update_unread_count_in_dom(get_filter_li(), count);
}

function remove_expanded_private_messages() {
    stream_popover.hide_topic_popover();
    ui.get_content_element($("#private-container")).empty();
}

export function close() {
    private_messages_open = false;
    prior_dom = undefined;
    remove_expanded_private_messages();
}

export function _build_private_messages_list() {
    const conversations = pm_list_data.get_conversations();
    const dom_ast = pm_list_dom.pm_ul(conversations);
    return dom_ast;
}

export function update_private_messages() {
    if (!narrow_state.active()) {
        return;
    }

    if (private_messages_open) {
        const $container = ui.get_content_element($("#private-container"));
        const new_dom = _build_private_messages_list();

        function replace_content(html) {
            $container.html(html);
        }

        function find() {
            return $container.find("ul");
        }

        vdom.update(replace_content, find, new_dom, prior_dom);
        prior_dom = new_dom;
    }
}

export function expand() {
    private_messages_open = true;
    stream_popover.hide_topic_popover();
    update_private_messages();
    if (pm_list_data.is_all_privates()) {
        $(".top_left_private_messages").addClass("active-filter");
    }
}

export function update_dom_with_unread_counts(counts) {
    update_private_messages();
    set_count(counts.private_message_count);
}

function should_expand_pm_list(filter) {
    const op_is = filter.operands("is");

    if (op_is.length >= 1 && op_is.includes("private")) {
        return true;
    }

    const op_pm = filter.operands("pm-with");

    if (op_pm.length !== 1) {
        return false;
    }

    const emails_strings = op_pm[0];
    const emails = emails_strings.split(",");

    const has_valid_emails = people.is_valid_bulk_emails_for_compose(emails);

    return has_valid_emails;
}

export function handle_narrow_activated(filter) {
    if (should_expand_pm_list(filter)) {
        expand();
    } else {
        close();
    }
}

export function handle_narrow_deactivated() {
    close();
}
