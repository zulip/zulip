import $ from "jquery";

import render_more_pms from "../templates/more_pms.hbs";

import * as buddy_data from "./buddy_data";
import * as hash_util from "./hash_util";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as pm_conversations from "./pm_conversations";
import * as pm_list_dom from "./pm_list_dom";
import * as resize from "./resize";
import * as stream_popover from "./stream_popover";
import * as ui from "./ui";
import * as ui_util from "./ui_util";
import * as unread from "./unread";
import * as vdom from "./vdom";

let prior_dom;
let private_messages_open = true;
let zoomed_pm_list = false;

export function show_more_pms() {
    zoomed_pm_list = true;
}

export function hide_more_pms() {
    zoomed_pm_list = false;
}

export function clear_for_testing() {
    prior_dom = undefined;
}

// This module manages the "Private messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

function get_filter_li() {
    return $("#private_messages #private_messages_header");
}

function set_count(count) {
    ui_util.update_unread_count_in_dom(get_filter_li(), count);
}

function remove_expanded_private_messages() {
    stream_popover.hide_topic_popover();
    const active_convo_li = $(".expanded_private_messages li.active-sub-filter");
    $(".expanded_private_messages").empty().append(active_convo_li);
}

export function close() {
    private_messages_open = false;
    prior_dom = undefined;
    remove_expanded_private_messages();
}

export function get_active_user_ids_string() {
    const filter = narrow_state.filter();

    if (!filter) {
        return undefined;
    }

    const emails = filter.operands("pm-with")[0];

    if (!emails) {
        return undefined;
    }

    return people.emails_strings_to_user_ids_string(emails);
}

export function _get_convos() {
    const private_messages = pm_conversations.recent.get();
    const display_messages = [];
    const active_user_ids_string = get_active_user_ids_string();

    for (const private_message_obj of private_messages) {
        const user_ids_string = private_message_obj.user_ids_string;
        const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
        const recipients_string = people.get_recipients(user_ids_string);

        const num_unread = unread.num_unread_for_person(user_ids_string);

        const is_group = user_ids_string.includes(",");

        const is_active = user_ids_string === active_user_ids_string;

        let user_circle_class;

        if (!is_group) {
            const user_id = Number.parseInt(user_ids_string, 10);
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
            is_group,
        };
        display_messages.push(display_message);
    }

    return display_messages;
}

export function more_pms() {
    const render = () => render_more_pms();

    const eq = (other) => other.more_items;

    const key = "more";

    return {
        key,
        more_items: true,
        render,
        eq,
    };
}

export function _build_private_messages_list() {
    const convos = _get_convos();
    let convos_to_be_shown = convos;
    let nodes;
    if (zoomed_pm_list) {
        nodes = convos_to_be_shown.map((convo) => pm_list_dom.keyed_pm_li(convo));
    } else {
        if (convos.length > 4) {
            convos_to_be_shown = convos.slice(0, 4);
            const active_convo = convos.find((convo) => {
                if (convo.is_active === true) {
                    return convo;
                }
                return false;
            });
            if (active_convo && !convos_to_be_shown.includes(active_convo)) {
                convos_to_be_shown.push(active_convo);
            }
            nodes = convos_to_be_shown.map((convo) => pm_list_dom.keyed_pm_li(convo));
            if (convos_to_be_shown.length !== convos.length) {
                nodes.push(more_pms());
            }
        } else {
            nodes = convos_to_be_shown.map((convo) => pm_list_dom.keyed_pm_li(convo));
        }
    }

    const dom_ast = pm_list_dom.pm_ul(nodes);
    return dom_ast;
}

export function update_private_messages() {
    if (private_messages_open) {
        const container = ui.get_content_element($("#private-container"));
        const new_dom = _build_private_messages_list();

        function replace_content(html) {
            container.html(html);
        }

        function find() {
            return container.find("ul");
        }

        vdom.update(replace_content, find, new_dom, prior_dom);
        prior_dom = new_dom;
    }
}

export function is_all_privates() {
    const filter = narrow_state.filter();

    if (!filter) {
        return false;
    }

    return filter.operands("is").includes("private");
}

export function expand() {
    private_messages_open = true;
    stream_popover.hide_topic_popover();
    update_private_messages();
    if (is_all_privates()) {
        $("#private-container").addClass("active-filter");
    }
}

export function update_dom_with_unread_counts(counts) {
    update_private_messages();
    set_count(counts.private_message_count);
}

export function handle_narrow_activated(filter) {
    const active_filter = filter;
    if (active_filter.operands("pm-with").length !== 0) {
        expand();
    } else {
        if (
            $(".expanded_private_messages").children().length === 1 &&
            $(".expanded_private_messages li.active-sub-filter").is(
                $(".expanded_private_messages").children()[0],
            )
        ) {
            $(".expanded_private_messages").empty();
            close();
        }
        $(".expanded_private_messages li.active-sub-filter").removeClass("active-sub-filter");
    }
}

export function handle_narrow_deactivated() {
    hide_more_pms();
    update_private_messages();
    $("#private_messages").removeClass("zoom-in").addClass("zoom-out");
    $("#streams_list").show();
    $(".left-sidebar .right-sidebar-items").show();
    if (
        $(".expanded_private_messages").children().length === 1 &&
        $(".expanded_private_messages li.active-sub-filter").is(
            $(".expanded_private_messages").children()[0],
        )
    ) {
        $(".expanded_private_messages").empty();
    }
    $(".expanded_private_messages li.active-sub-filter").removeClass("active-sub-filter");
    setTimeout(() => {
        resize.resize_sidebars();
    }, 0);
}

export function initialize() {
    $("#private_messages").on("click", "#show_more_pms", (e) => {
        e.stopPropagation();
        e.preventDefault();
        show_more_pms();
        update_private_messages();
        $("#private_messages").removeClass("zoom-out").addClass("zoom-in");
        $("#streams_list").hide();
        $(".left-sidebar .right-sidebar-items").hide();
    });

    $("#private_messages").on("click", "#more_pms_header", (e) => {
        e.stopPropagation();
        e.preventDefault();
        hide_more_pms();
        update_private_messages();
        $("#private_messages").removeClass("zoom-in").addClass("zoom-out");
        $("#streams_list").show();
        setTimeout(() => {
            resize.resize_sidebars();
        }, 0);
        $(".left-sidebar .right-sidebar-items").show();
    });
}
