import $ from "jquery";

import render_more_pms from "../templates/more_pms.hbs";

import * as buddy_data from "./buddy_data";
import * as hash_util from "./hash_util";
import {localstorage} from "./localstorage";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as pm_conversations from "./pm_conversations";
import * as pm_list_data from "./pm_list_data";
import * as pm_list_dom from "./pm_list_dom";
import * as resize from "./resize";
import * as stream_popover from "./stream_popover";
import * as ui from "./ui";
import * as ui_util from "./ui_util";
import * as unread from "./unread";
import * as user_status from "./user_status";
import * as vdom from "./vdom";

let prior_dom;

// To keep a track of state of private messages.
let private_messages_collapsed = false;

// To keep a track whether we're zoomed or not.
let zoomed = false;

// Use localstorage library.
const ls = localstorage();

export function show_more_pms() {
    zoomed = true;
}

export function hide_more_pms() {
    zoomed = false;
}

export function clear_for_testing() {
    prior_dom = undefined;
}

export function return_private_messages_state() {
    // This function returns the state of PM section which
    // we use to toggle the PM section UI through click handlers.js
    return private_messages_collapsed;
}

// This module manages the "Private messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

function get_filter_li() {
    return $("#private_messages .private-messages-section-header");
}

function set_count(count) {
    ui_util.update_unread_count_in_dom(get_filter_li(), count);
}

function remove_expanded_private_messages() {
    stream_popover.hide_topic_popover();
    // While making the private messages list empty
    // we check for any active pm conversation thread present in it and
    // append it inside the PM section.
    const active_convo_li = $(".expanded-private-messages li.active-sub-filter");
    $(".expanded-private-messages").empty().append(active_convo_li);
}

export function close() {
    // Set the localstorage variable of `private_messages_collapsed` as `true`.
    if (localstorage.supported()) {
        ls.set("private_messages_collapsed", true);
    }
    private_messages_collapsed = true;
    remove_expanded_private_messages();
    prior_dom = undefined;
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
        let status_emoji_info;

        if (!is_group) {
            const user_id = Number.parseInt(user_ids_string, 10);
            user_circle_class = buddy_data.get_user_circle_class(user_id);
            const recipient_user_obj = people.get_by_user_id(user_id);

            if (recipient_user_obj.is_bot) {
                user_circle_class = "user_circle_green";
                // bots do not have status emoji
            } else {
                status_emoji_info = user_status.get_status_emoji(user_id);
            }
        }

        const display_message = {
            recipients: recipients_string,
            user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_active,
            url: hash_util.pm_with_url(reply_to),
            status_emoji_info,
            user_circle_class,
            is_group,
        };
        display_messages.push(display_message);
    }

    return display_messages;
}

export function more_pms(more_convos_unread_count) {
    // we render the li-item of `more conversations` with the unreads count inside the dom.
    const render = () => render_more_pms({more_convos_unread_count});

    const eq = (other) =>
        other.more_items && more_convos_unread_count === other.more_convos_unread_count;

    const key = "more";

    return {
        key,
        more_items: true,
        more_convos_unread_count,
        render,
        eq,
    };
}

export function _build_private_messages_list() {
    const convos = _get_convos();
    const pm_list_info = pm_list_data.get_list_info(zoomed);
    const convos_to_be_shown = pm_list_info.convos_to_be_shown;
    const more_convos_unread_count = pm_list_info.more_convos_unread_count;

    const nodes = convos_to_be_shown.map((convo) => pm_list_dom.keyed_pm_li(convo));

    const is_showing_all_possible_private_messages_threads =
        convos_to_be_shown.length === convos.length;
    if (!is_showing_all_possible_private_messages_threads) {
        nodes.push(more_pms(more_convos_unread_count));
    }
    const dom_ast = pm_list_dom.pm_ul(nodes);
    return dom_ast;
}

export function update_private_messages() {
    // we preserve the state of PM section (collapsed/expanded) in localstorage.
    if (localstorage.supported()) {
        // Check if there exists a value with key "private_messages_collapsed" in localstorage
        // else keep PM section as `expanded` by-default.
        if (ls.get("private_messages_collapsed") !== undefined) {
            private_messages_collapsed = ls.get("private_messages_collapsed");
        } else {
            private_messages_collapsed = false;
        }
    }
    if (!private_messages_collapsed) {
        const container = ui.get_content_element($("#private_messages_container"));
        const new_dom = _build_private_messages_list();

        function replace_content(html) {
            container.html(html);
        }

        function find() {
            return container.find("ul");
        }

        vdom.update(replace_content, find, new_dom, prior_dom);
        prior_dom = new_dom;
    } else {
        // If we collapse the PM section with 1 active PM outside of it, then we append it again while
        // preserving the state of PM section.
        append_new_active_pm_in_collapsed_pms();

        // Change the toggle icon of private_messages_section to collapsed if
        // we have `private_messages_collapsed` as `true`
        $("#toggle_private_messages_section_icon").removeClass("'fa fa-caret-down fa-lg'");
        $("#toggle_private_messages_section_icon").addClass("'fa fa-caret-right fa-lg'");
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
    // Set the localstorage variable of `private_messages_collapsed` as `false`.
    if (localstorage.supported()) {
        ls.set("private_messages_collapsed", false);
    }
    private_messages_collapsed = false;
    stream_popover.hide_topic_popover();
    update_private_messages();
    if (is_all_privates()) {
        $("#private_messages_container").addClass("active-filter");
    }
}

export function update_dom_with_unread_counts(counts) {
    update_private_messages();
    set_count(counts.private_message_count);
}

export function only_active_pm_out_of_collapsed_pms() {
    // check for the presence of only active pm outside the list of the collapsed pms.
    if (
        $(".expanded-private-messages").children().length === 1 &&
        $(".expanded-private-messages li.active-sub-filter").is(
            $(".expanded-private-messages").children()[0],
        )
    ) {
        return true;
    }
    return false;
}

export function append_new_active_pm_in_collapsed_pms() {
    // We check for the new activated PM thread in our DOM and append it inside the list of pms visible out of
    // collapsed pms.
    const convos = _get_convos();
    const active_convo = convos.find((convo) => {
        if (convo.is_active === true) {
            return convo;
        }
        return false;
    });
    if (active_convo) {
        // If we find a the new active PM to be present in out convos list then we make a node of it
        // through keyed_pm_li and update the DOM with vdom.update() function.
        const node = [pm_list_dom.keyed_pm_li(active_convo)];
        const new_dom = pm_list_dom.pm_ul(node);
        const container = ui.get_content_element($("#private_messages_container"));
        function replace_content(html) {
            container.html(html);
        }

        function find() {
            return container.find("ul");
        }
        vdom.update(replace_content, find, new_dom, prior_dom);
        prior_dom = new_dom;
    } else {
        // If we do not find any other active pm in our convos then we clear the list of PMs and
        // collapse the section.
        $(".expanded-private-messages").empty();
        close();
    }
}

export function activate_all_private_messages_view() {
    $("#private_messages_section").addClass("active_private_messages_section");
    $(".more-private-messages-sidebar-title").css("font-weight", "bold");
}

export function deactivate_all_private_messages_view() {
    $("#private_messages_section").removeClass("active_private_messages_section");
    $(".more-private-messages-sidebar-title").css("font-weight", "normal");
}

export function handle_narrow_activated(filter) {
    const active_filter = filter;
    // We check whether the new narrow is also related to a PM thread or not
    if (active_filter.operands("pm-with").length !== 0) {
        // If we find the new narrow to also be a PM thread then check for number of PMs present and state of PM section
        if (
            // If we find all PMs to be collapsed and only 1 previously active PM outside of the collapsed
            // pms, then we remove the previous one and append the newly active PM inside the collapsed PMs.
            only_active_pm_out_of_collapsed_pms()
        ) {
            append_new_active_pm_in_collapsed_pms();
        }
        // After activating narrow for a PM thread, we deactivate the `All private messages` view.
        deactivate_all_private_messages_view();
    } else {
        // If we find no PMs in narrow filter and we see that state of PM section is
        // suppose to be collapsed we then empty out the list of PMs and close it.
        if (private_messages_collapsed) {
            $(".expanded-private-messages").empty();
            close();
        }
        // We always deactivate the previously activated PM in case of new narrow not belonging to PMs.
        $(".expanded-private-messages li.active-sub-filter").removeClass("active-sub-filter");
    }
}

export function handle_narrow_deactivated() {
    // In case of the new narrow not belonging to PMs, we revert the state of current PM section
    // to it's initial state (even in the cae of zoomed PM section) and deactivate the previously activated
    // PM and resize the stream bar again.
    hide_more_pms();
    deactivate_all_private_messages_view();
    $("#private_messages").removeClass("zoom-in").addClass("zoom-out");
    $("#streams_list").show();
    $(".left-sidebar .right-sidebar-items").show();
    if (private_messages_collapsed) {
        $(".expanded-private-messages").empty();
        close();
    }
    $(".expanded-private-messages li.active-sub-filter").removeClass("active-sub-filter");
    update_private_messages();
    setTimeout(() => {
        resize.resize_stream_filters_container();
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
        setTimeout(() => {
            resize.resize_stream_filters_container();
        }, 0);
    });

    $("#private_messages").on("click", "#hide_more_pms", (e) => {
        e.stopPropagation();
        e.preventDefault();
        hide_more_pms();
        update_private_messages();
        $("#private_messages").removeClass("zoom-in").addClass("zoom-out");
        $("#streams_list").show();
        $(".left-sidebar .right-sidebar-items").show();
        setTimeout(() => {
            resize.resize_stream_filters_container();
        }, 0);
    });
}
