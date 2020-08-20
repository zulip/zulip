"use strict";

const people = require("./people");
const pm_conversations = require("./pm_conversations");

let prior_dom;
let private_messages_open = false;

// This module manages the "Private Messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

function get_filter_li() {
    return $(".top_left_private_messages");
}

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        value_span.text("");
    } else {
        count_span.show();
        value_span.text(count);
    }
}

function set_count(count) {
    const count_span = get_filter_li().find(".count");
    const value_span = count_span.find(".value");
    update_count_in_dom(count_span, value_span, count);
}

function remove_expanded_private_messages() {
    stream_popover.hide_topic_popover();
    ui.get_content_element($("#private-container")).empty();
}

exports.close = function () {
    private_messages_open = false;
    prior_dom = undefined;
    remove_expanded_private_messages();
};

exports.get_active_user_ids_string = function () {
    const filter = narrow_state.filter();

    if (!filter) {
        return;
    }

    const emails = filter.operands("pm-with")[0];

    if (!emails) {
        return;
    }

    return people.emails_strings_to_user_ids_string(emails);
};

exports._get_convos = function () {
    const private_messages = pm_conversations.recent.get();
    const display_messages = [];
    const active_user_ids_string = exports.get_active_user_ids_string();

    for (const private_message_obj of private_messages) {
        const user_ids_string = private_message_obj.user_ids_string;
        const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
        const recipients_string = people.get_recipients(user_ids_string);

        const num_unread = unread.num_unread_for_person(user_ids_string);

        const is_group = user_ids_string.includes(",");

        const is_active = user_ids_string === active_user_ids_string;

        let user_circle_class;
        let fraction_present;

        if (is_group) {
            user_circle_class = "user_circle_fraction";
            fraction_present = buddy_data.huddle_fraction_present(user_ids_string);
        } else {
            const user_id = parseInt(user_ids_string, 10);
            user_circle_class = buddy_data.get_user_circle_class(user_id);
            const recipient_user_obj = people.get_by_user_id(user_id);

            if (recipient_user_obj.is_bot) {
                user_circle_class = "user_circle_green";
            }
        }

        const display_message = {
            recipients: recipients_string,
            user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_active,
            url: hash_util.pm_with_uri(reply_to),
            user_circle_class,
            fraction_present,
            is_group,
        };
        display_messages.push(display_message);
    }

    return display_messages;
};

exports._build_private_messages_list = function () {
    const finish = blueslip.start_timing("render pm list");
    const convos = exports._get_convos();
    const dom_ast = pm_list_dom.pm_ul(convos);
    finish();
    return dom_ast;
};

exports.update_private_messages = function () {
    if (!narrow_state.active()) {
        return;
    }

    if (private_messages_open) {
        const container = ui.get_content_element($("#private-container"));
        const new_dom = exports._build_private_messages_list();

        function replace_content(html) {
            container.html(html);
        }

        function find() {
            return container.find("ul");
        }

        vdom.update(replace_content, find, new_dom, prior_dom);
        prior_dom = new_dom;
    }
};

exports.is_all_privates = function () {
    const filter = narrow_state.filter();

    if (!filter) {
        return false;
    }

    return filter.operands("is").includes("private");
};

exports.expand = function () {
    private_messages_open = true;
    stream_popover.hide_topic_popover();
    exports.update_private_messages();
    if (exports.is_all_privates()) {
        $(".top_left_private_messages").addClass("active-filter");
    }
};

exports.update_dom_with_unread_counts = function (counts) {
    exports.update_private_messages();
    set_count(counts.private_message_count);
    unread_ui.set_count_toggle_button(
        $("#userlist-toggle-unreadcount"),
        counts.private_message_count,
    );
};

exports.initialize = function () {};

window.pm_list = exports;
