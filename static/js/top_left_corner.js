"use strict";

const people = require("./people");

exports.update_count_in_dom = function (unread_count_elem, count) {
    const count_span = unread_count_elem.find(".count");
    const value_span = count_span.find(".value");

    if (count === 0) {
        count_span.hide();
        value_span.text("");
        return;
    }

    count_span.show();
    value_span.text(count);
};

exports.update_starred_count = function (count) {
    const starred_li = $(".top_left_starred_messages");
    exports.update_count_in_dom(starred_li, count);
};

exports.update_dom_with_unread_counts = function (counts) {
    // Note that "Private messages" counts are handled in pm_list.js.

    // mentioned/home have simple integer counts
    const mentioned_li = $(".top_left_mentions");
    const home_li = $(".top_left_all_messages");

    exports.update_count_in_dom(mentioned_li, counts.mentioned_message_count);
    exports.update_count_in_dom(home_li, counts.home_unread_messages);

    unread_ui.animate_mention_changes(mentioned_li, counts.mentioned_message_count);
};

function remove(elem) {
    elem.removeClass("active-filter active-sub-filter");
}

function deselect_top_left_corner_items() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_private_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_recent_topics"));
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

exports.handle_narrow_activated = function (filter) {
    deselect_top_left_corner_items();

    let ops;
    let filter_name;
    let filter_li;

    // TODO: handle confused filters like "in:all stream:foo"
    ops = filter.operands("in");
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === "home") {
            filter_li = $(".top_left_all_messages");
            filter_li.addClass("active-filter");
        }
    }
    ops = filter.operands("is");
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === "starred") {
            filter_li = $(".top_left_starred_messages");
            filter_li.addClass("active-filter");
        } else if (filter_name === "mentioned") {
            filter_li = $(".top_left_mentions");
            filter_li.addClass("active-filter");
        }
    }

    if (should_expand_pm_list(filter)) {
        pm_list.expand();
    } else {
        pm_list.close();
    }
};

exports.handle_narrow_deactivated = function () {
    deselect_top_left_corner_items();
    pm_list.close();

    const filter_li = $(".top_left_all_messages");
    filter_li.addClass("active-filter");
};

exports.narrow_to_recent_topics = function () {
    remove($(".top_left_all_messages"));
    remove($(".top_left_private_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    $(".top_left_recent_topics").addClass("active-filter");
    pm_list.close();
};

window.top_left_corner = exports;
