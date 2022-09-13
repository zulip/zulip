import $ from "jquery";
import _ from "lodash";

import render_recent_topic_row from "../templates/recent_topic_row.hbs";
import render_recent_topics_filters from "../templates/recent_topics_filters.hbs";
import render_recent_topics_body from "../templates/recent_topics_table.hbs";

import * as buddy_data from "./buddy_data";
import * as compose_closed_ui from "./compose_closed_ui";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {localstorage} from "./localstorage";
import * as message_store from "./message_store";
import * as message_util from "./message_util";
import * as message_view_header from "./message_view_header";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as navigate from "./navigate";
import {page_params} from "./page_params";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as recent_senders from "./recent_senders";
import {get, process_message, topics} from "./recent_topics_data";
import {
    get_key_from_message,
    get_topic_key,
    is_in_focus,
    is_visible,
    set_visible,
} from "./recent_topics_util";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as top_left_corner from "./top_left_corner";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";
import * as user_topics from "./user_topics";

let topics_widget;
// Sets the number of avatars to display.
// Rest of the avatars, if present, are displayed as {+x}
const MAX_AVATAR = 4;
const MAX_EXTRA_SENDERS = 10;

// Use this to set the focused element.
//
// We set it's value to `table` in case the
// focus in one of the table rows, since the
// table rows are constantly updated and tracking
// the selected element in them would be tedious via
// jquery.
//
// So, we use table as a grid system and
// track the coordinates of the focus element via
// `row_focus` and `col_focus`.
export let $current_focus_elem = "table";

// If user clicks a topic in recent topics, then
// we store that topic here so that we can restore focus
// to that topic when user revisits.
let last_visited_topic = "";
let row_focus = 0;
// Start focus on the topic column, so Down+Enter works to visit a topic.
let col_focus = 1;

export const COLUMNS = {
    stream: 0,
    topic: 1,
    mute: 2,
    read: 3,
};

// The number of selectable actions in a recent_topics.  Used to
// implement wraparound of elements with the right/left keys.  Must be
// increased when we add new actions, or rethought if we add optional
// actions that only appear in some rows.
const MAX_SELECTABLE_TOPIC_COLS = 4;
const MAX_SELECTABLE_PM_COLS = 2;

// we use localstorage to persist the recent topic filters
const ls_key = "recent_topic_filters";
const ls = localstorage();

let filters = new Set();

export function clear_for_tests() {
    filters.clear();
    topics.clear();
    topics_widget = undefined;
}

export function save_filters() {
    ls.set(ls_key, Array.from(filters));
}

export function load_filters() {
    if (!page_params.is_spectator) {
        // A user may have a stored filter and can log out
        // to see web public view. This ensures no filters are
        // selected for spectators.
        filters = new Set(ls.get(ls_key));
    }
}

export function set_default_focus() {
    // If at any point we are confused about the currently
    // focused element, we switch focus to search.
    $current_focus_elem = $("#recent_topics_search");
    $current_focus_elem.trigger("focus");
    compose_closed_ui.set_standard_text_for_reply_button();
}

function get_min_load_count(already_rendered_count, load_count) {
    const extra_rows_for_viewing_pleasure = 15;
    if (row_focus > already_rendered_count + load_count) {
        return row_focus + extra_rows_for_viewing_pleasure - already_rendered_count;
    }
    return load_count;
}

function is_table_focused() {
    return $current_focus_elem === "table";
}

function get_row_type(row) {
    // Return "private" or "stream"
    // list_widget.clean_redraw() calls get_current_list before
    // the widget is returned and thus initialized.
    // So we use CSS method for finding row type until topics_widget gets initialized.
    if (!topics_widget) {
        const $topic_rows = $("#recent_topics_table table tbody tr");
        const $topic_row = $topic_rows.eq(row);
        const type = $topic_row.find(".recent_topic_stream a").text();
        if (type === "Private messages") {
            return "private";
        }
        return "stream";
    }

    const current_list = topics_widget.get_current_list();
    const current_row = current_list[row];
    return current_row.type;
}

function get_max_selectable_cols(row) {
    // returns maximum number of columns in stream message or private message row.
    const type = get_row_type(row);
    if (type === "private") {
        return MAX_SELECTABLE_PM_COLS;
    }
    return MAX_SELECTABLE_TOPIC_COLS;
}

function set_table_focus(row, col, using_keyboard) {
    const $topic_rows = $("#recent_topics_table table tbody tr");
    if ($topic_rows.length === 0 || row < 0 || row >= $topic_rows.length) {
        row_focus = 0;
        // return focus back to filters if we cannot focus on the table.
        set_default_focus();
        return true;
    }

    const $topic_row = $topic_rows.eq(row);
    // We need to allow table to render first before setting focus.
    setTimeout(
        () => $topic_row.find(".recent_topics_focusable").eq(col).children().trigger("focus"),
        0,
    );
    $current_focus_elem = "table";

    if (using_keyboard) {
        const scroll_element = document.querySelector(
            "#recent_topics_table .table_fix_head .simplebar-content-wrapper",
        );
        const half_height_of_visible_area = scroll_element.offsetHeight / 2;
        const topic_offset = topic_offset_to_visible_area($topic_row);

        if (topic_offset === "above") {
            scroll_element.scrollBy({top: -1 * half_height_of_visible_area});
        } else if (topic_offset === "below") {
            scroll_element.scrollBy({top: half_height_of_visible_area});
        }
    }

    const type = get_row_type(row);
    let message;
    if (type === "private") {
        message = {
            recipients: $topic_row.find(".recent_topic_name a").text(),
        };
    } else {
        message = {
            stream: $topic_row.find(".recent_topic_stream a").text(),
            topic: $topic_row.find(".recent_topic_name a").text(),
        };
    }
    compose_closed_ui.update_reply_recipient_label(message);
    return true;
}

export function get_focused_row_message() {
    const recent_conversation_id_prefix_len = "recent_conversation:".length;

    if (is_table_focused()) {
        const $topic_rows = $("#recent_topics_table table tbody tr");
        if ($topic_rows.length === 0) {
            return undefined;
        }

        const $topic_row = $topic_rows.eq(row_focus);
        const conversation_id = $topic_row.attr("id").slice(recent_conversation_id_prefix_len);
        const topic_last_msg_id = topics.get(conversation_id).last_msg_id;
        return message_store.get(topic_last_msg_id);
    }
    return undefined;
}

export function revive_current_focus() {
    // After re-render, the current_focus_elem is no longer linked
    // to the focused element, this function attempts to revive the
    // link and focus to the element prior to the rerender.

    // We try to avoid setting focus when user
    // is not focused on recent topics.
    if (!is_in_focus()) {
        return false;
    }

    if (!$current_focus_elem) {
        set_default_focus();
        return false;
    }

    if (is_table_focused()) {
        if (last_visited_topic) {
            // If the only message in the topic was deleted,
            // then the topic will not be in recent topics data.
            if (topics.get(last_visited_topic) !== undefined) {
                const topic_last_msg_id = topics.get(last_visited_topic).last_msg_id;
                const current_list = topics_widget.get_current_list();
                const last_visited_topic_index = current_list.findIndex(
                    (topic) => topic.last_msg_id === topic_last_msg_id,
                );
                if (last_visited_topic_index >= 0) {
                    row_focus = last_visited_topic_index;
                }
            }
            last_visited_topic = "";
        }
        set_table_focus(row_focus, col_focus);
        return true;
    }

    const filter_button = $current_focus_elem.data("filter");
    if (!filter_button) {
        set_default_focus();
    } else {
        $current_focus_elem = $("#recent_topics_filter_buttons").find(
            `[data-filter='${CSS.escape(filter_button)}']`,
        );
        $current_focus_elem.trigger("focus");
    }
    return true;
}

export function show_loading_indicator() {
    loading.make_indicator($("#recent_topics_loading_messages_indicator"));
}

export function hide_loading_indicator() {
    $("#recent_topics_bottom_whitespace").hide();
    loading.destroy_indicator($("#recent_topics_loading_messages_indicator"), {
        abs_positioned: false,
    });
    // Show empty table text if there are no messages fetched.
    $("#recent_topics_table tbody").addClass("required-text");
}

export function process_messages(messages) {
    // While this is inexpensive and handles all the cases itself,
    // the UX can be bad if user wants to scroll down the list as
    // the UI will be returned to the beginning of the list on every
    // update.
    //
    // Only rerender if topic_data actually
    // changed.
    let topic_data_changed = false;
    for (const msg of messages) {
        if (process_message(msg)) {
            topic_data_changed = true;
        }
    }

    if (topic_data_changed) {
        complete_rerender();
    }
}

function format_message(msg_data) {
    const msg_info = {};
    const last_msg = message_store.get(msg_data.last_msg_id);
    const time = new Date(last_msg.timestamp * 1000);
    const type = last_msg.type;
    msg_info.full_last_msg_date_time = timerender.get_full_datetime(time);
    msg_info.conversation_key = get_key_from_message(last_msg);
    msg_info.unread_count = unread.get_thread_unread_count_from_message(last_msg);
    msg_info.last_msg_time = timerender.last_seen_status_from_date(time);
    let displayed_other_names;
    let extra_sender_ids;

    if (type === "stream") {
        const stream_info = sub_store.get(last_msg.stream_id);

        // Stream info
        msg_info.stream_id = last_msg.stream_id;
        msg_info.stream = last_msg.stream;
        msg_info.stream_color = stream_info.color;
        msg_info.stream_url = hash_util.by_stream_url(msg_info.stream_id);
        msg_info.invite_only = stream_info.invite_only;
        msg_info.is_web_public = stream_info.is_web_public;

        // Topic info
        msg_info.topic = last_msg.topic;
        msg_info.topic_url = hash_util.by_stream_topic_url(msg_info.stream_id, msg_info.topic);

        // We hide the row according to filters or if it's muted.
        // We only supply the data to the topic rows and let jquery
        // display / hide them according to filters instead of
        // doing complete re-render.
        msg_info.topic_muted = Boolean(
            user_topics.is_topic_muted(msg_info.stream_id, msg_info.topic),
        );
        const stream_muted = stream_data.is_muted(msg_info.stream_id);
        msg_info.muted = msg_info.topic_muted || stream_muted;

        // Display in most recent sender first order
        const all_senders = recent_senders.get_topic_recent_senders(
            msg_info.stream_id,
            msg_info.topic,
        );
        const senders = all_senders.slice(-MAX_AVATAR);
        msg_info.senders = people.sender_info_for_recent_topics_row(senders);
        msg_info.other_senders_count = Math.max(0, all_senders.length - MAX_AVATAR);

        // Collect extra sender fullname for tooltip
        extra_sender_ids = all_senders.slice(0, -MAX_AVATAR);
        const displayed_other_senders = extra_sender_ids.slice(-MAX_EXTRA_SENDERS);
        displayed_other_names = people.get_display_full_names(displayed_other_senders.reverse());
    } else if (type === "private") {
        // Private message info
        msg_info.pm_with = last_msg.display_reply_to;
        msg_info.recipient_id = last_msg.recipient_id;
        msg_info.pm_url = last_msg.pm_with_url;
        msg_info.is_private = last_msg.type = "private";
        msg_info.is_group = last_msg.display_recipient.length > 2;

        // Display in most recent sender first order
        const all_senders = last_msg.display_recipient;
        const senders = all_senders.slice(-MAX_AVATAR).map((sender) => sender.id);
        msg_info.senders = people.sender_info_for_recent_topics_row(senders);
        msg_info.other_senders_count = Math.max(0, all_senders.length - MAX_AVATAR);

        if (!msg_info.is_group) {
            msg_info.user_circle_class = buddy_data.get_user_circle_class(
                Number.parseInt(last_msg.to_user_ids, 10),
            );
        }

        // Collect extra senders fullname for tooltip.
        extra_sender_ids = all_senders.slice(0, -MAX_AVATAR);
        const displayed_other_senders = extra_sender_ids
            .slice(-MAX_EXTRA_SENDERS)
            .map((sender) => sender.id);
        displayed_other_names = people.get_display_full_names(displayed_other_senders.reverse());
    }

    if (extra_sender_ids.length > MAX_EXTRA_SENDERS) {
        // We display only 10 extra senders in tooltips,
        // and just display remaining number of senders.
        const remaining_senders = extra_sender_ids.length - MAX_EXTRA_SENDERS;
        // Pluralization syntax from:
        // https://formatjs.io/docs/core-concepts/icu-syntax/#plural-format
        displayed_other_names.push(
            $t(
                {
                    defaultMessage:
                        "and {remaining_senders, plural, one {1 other} other {# others}}.",
                },
                {remaining_senders},
            ),
        );
    }
    msg_info.other_sender_names_html = displayed_other_names
        .map((name) => _.escape(name))
        .join("<br />");
    msg_info.participated = msg_data.participated;
    msg_info.last_msg_url = hash_util.by_conversation_and_time_url(last_msg);

    return msg_info;
}

function get_topic_row(topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);
    const topic_key = get_key_from_message(msg);
    return $(`#${CSS.escape("recent_conversation:" + topic_key)}`);
}

export function process_topic_edit(old_stream_id, old_topic, new_topic, new_stream_id) {
    // See `recent_senders.process_topic_edit` for
    // logic behind this and important notes on use of this function.
    topics.delete(get_topic_key(old_stream_id, old_topic));

    const old_topic_msgs = message_util.get_messages_in_topic(old_stream_id, old_topic);
    process_messages(old_topic_msgs);

    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_messages_in_topic(new_stream_id, new_topic);
    process_messages(new_topic_msgs);
}

export function topic_in_search_results(keyword, stream, topic) {
    if (keyword === "") {
        return true;
    }
    const text = (stream + " " + topic).toLowerCase();
    const search_words = keyword.toLowerCase().split(/\s+/);
    return search_words.every((word) => text.includes(word));
}

export function update_topics_of_deleted_message_ids(message_ids) {
    const topics_to_rerender = message_util.get_topics_for_message_ids(message_ids);

    for (const [stream_id, topic] of topics_to_rerender.values()) {
        topics.delete(get_topic_key(stream_id, topic));
        const msgs = message_util.get_messages_in_topic(stream_id, topic);
        process_messages(msgs);
    }
}

export function filters_should_hide_topic(topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);
    const sub = sub_store.get(msg.stream_id);

    if ((sub === undefined || !sub.subscribed) && topic_data.type === "stream") {
        // Never try to process deactivated & unsubscribed stream msgs.
        return true;
    }

    if (filters.has("unread")) {
        const unread_count = unread.get_thread_unread_count_from_message(msg);
        if (unread_count === 0) {
            return true;
        }
    }

    if (!topic_data.participated && filters.has("participated")) {
        return true;
    }

    if (!filters.has("include_muted") && topic_data.type === "stream") {
        const topic_muted = Boolean(user_topics.is_topic_muted(msg.stream_id, msg.topic));
        const stream_muted = stream_data.is_muted(msg.stream_id);
        if (topic_muted || stream_muted) {
            return true;
        }
    }

    if (filters.has("include_private") && topic_data.type === "private") {
        return true;
    }

    const search_keyword = $("#recent_topics_search").val();
    if (!topic_in_search_results(search_keyword, msg.stream, msg.topic)) {
        return true;
    }

    return false;
}

export function inplace_rerender(topic_key) {
    if (!is_visible()) {
        return false;
    }
    if (!topics.has(topic_key)) {
        return false;
    }

    const topic_data = topics.get(topic_key);
    topics_widget.render_item(topic_data);
    const topic_row = get_topic_row(topic_data);

    if (filters_should_hide_topic(topic_data)) {
        topic_row.hide();
    } else {
        topic_row.show();
    }
    revive_current_focus();
    return true;
}

export function update_topic_is_muted(stream_id, topic) {
    const key = get_topic_key(stream_id, topic);
    if (!topics.has(key)) {
        // we receive mute request for a topic we are
        // not tracking currently
        return false;
    }

    inplace_rerender(key);
    return true;
}

export function update_topic_unread_count(message) {
    const topic_key = get_key_from_message(message);
    inplace_rerender(topic_key);
}

export function set_filter(filter) {
    // This function updates the `filters` variable
    // after user clicks on one of the filter buttons
    // based on `btn-recent-selected` class and current
    // set `filters`.

    // Get the button which was clicked.
    const $filter_elem = $("#recent_topics_filter_buttons").find(
        `[data-filter="${CSS.escape(filter)}"]`,
    );

    // If user clicks `All`, we clear all filters.
    if (filter === "all" && filters.size !== 0) {
        filters = new Set();
        // If the button was already selected, remove the filter.
    } else if ($filter_elem.hasClass("btn-recent-selected")) {
        filters.delete(filter);
        // If the button was not selected, we add the filter.
    } else {
        filters.add(filter);
    }

    save_filters();
}

function show_selected_filters() {
    // Add `btn-selected-filter` to the buttons to show
    // which filters are applied.
    if (filters.size === 0) {
        $("#recent_topics_filter_buttons")
            .find('[data-filter="all"]')
            .addClass("btn-recent-selected")
            .attr("aria-checked", "true");
    } else {
        for (const filter of filters) {
            $("#recent_topics_filter_buttons")
                .find(`[data-filter="${CSS.escape(filter)}"]`)
                .addClass("btn-recent-selected")
                .attr("aria-checked", "true");
        }
    }
}

export function update_filters_view() {
    const rendered_filters = render_recent_topics_filters({
        filter_participated: filters.has("participated"),
        filter_unread: filters.has("unread"),
        filter_muted: filters.has("include_muted"),
        filter_pm: filters.has("include_private"),
        is_spectator: page_params.is_spectator,
    });
    $("#recent_filters_group").html(rendered_filters);
    show_selected_filters();

    topics_widget.hard_redraw();
}

function sort_comparator(a, b) {
    // compares strings in lowercase and returns -1, 0, 1
    if (a.toLowerCase() > b.toLowerCase()) {
        return 1;
    } else if (a === b) {
        return 0;
    }
    return -1;
}

function stream_sort(a, b) {
    if (a.type === b.type) {
        const a_msg = message_store.get(a.last_msg_id);
        const b_msg = message_store.get(b.last_msg_id);

        if (a.type === "stream") {
            return sort_comparator(a_msg.stream, b_msg.stream);
        }
        return sort_comparator(a_msg.display_reply_to, b_msg.display_reply_to);
    }
    // if type is not same sort between "private" and "stream"
    return sort_comparator(a.type, b.type);
}

function topic_sort(a, b) {
    const a_msg = message_store.get(a.last_msg_id);
    const b_msg = message_store.get(b.last_msg_id);

    if (a_msg.type === b_msg.type) {
        if (a_msg.type === "private") {
            return sort_comparator(a_msg.display_reply_to, b_msg.display_reply_to);
        }
        return sort_comparator(a_msg.topic, b_msg.topic);
    } else if (a_msg.type === "private") {
        return sort_comparator(a_msg.display_reply_to, b_msg.topic);
    }
    return sort_comparator(a_msg.topic, b_msg.display_reply_to);
}

function topic_offset_to_visible_area(topic_row) {
    const $scroll_container = $("#recent_topics_table .table_fix_head");
    const thead_height = 30;
    const under_closed_compose_region_height = 50;

    const scroll_container_top = $scroll_container.offset().top + thead_height;
    const scroll_container_bottom =
        scroll_container_top + $scroll_container.height() - under_closed_compose_region_height;

    const topic_row_top = $(topic_row).offset().top;
    const topic_row_bottom = topic_row_top + $(topic_row).height();

    // Topic is above the visible scroll region.
    if (topic_row_top < scroll_container_top) {
        return "above";
        // Topic is below the visible scroll region.
    } else if (topic_row_bottom > scroll_container_bottom) {
        return "below";
    }

    // Topic is visible
    return "visible";
}

function set_focus_to_element_in_center() {
    const table_wrapper_element = document.querySelector("#recent_topics_table .table_fix_head");
    const $topic_rows = $("#recent_topics_table table tbody tr");

    if (row_focus > $topic_rows.length) {
        // User used a filter which reduced
        // the number of visible rows.
        return;
    }
    let $topic_row = $topic_rows.eq(row_focus);
    const topic_offset = topic_offset_to_visible_area($topic_row);
    if (topic_offset !== "visible") {
        // Get the element at the center of the table.
        const position = table_wrapper_element.getBoundingClientRect();
        const topic_center_x = (position.left + position.right) / 2;
        const topic_center_y = (position.top + position.bottom) / 2;

        $topic_row = $(document.elementFromPoint(topic_center_x, topic_center_y)).closest("tr");

        row_focus = $topic_rows.index($topic_row);
        set_table_focus(row_focus, col_focus);
    }
}

function is_scroll_position_for_render(scroll_container) {
    const table_bottom_margin = 100; // Extra margin at the bottom of table.
    const table_row_height = 50;
    return (
        scroll_container.scrollTop +
            scroll_container.clientHeight +
            table_bottom_margin +
            table_row_height >
        scroll_container.scrollHeight
    );
}

export function complete_rerender() {
    if (!is_visible()) {
        return;
    }

    // Update header
    load_filters();
    show_selected_filters();

    // Show topics list
    const mapped_topic_values = Array.from(get().values()).map((value) => value);

    if (topics_widget) {
        topics_widget.replace_list_data(mapped_topic_values);
        return;
    }

    const rendered_body = render_recent_topics_body({
        filter_participated: filters.has("participated"),
        filter_unread: filters.has("unread"),
        filter_muted: filters.has("include_muted"),
        filter_pm: filters.has("include_private"),
        search_val: $("#recent_topics_search").val() || "",
        is_spectator: page_params.is_spectator,
    });
    $("#recent_topics_table").html(rendered_body);
    const $container = $("#recent_topics_table table tbody");
    $container.empty();
    topics_widget = ListWidget.create($container, mapped_topic_values, {
        name: "recent_topics_table",
        $parent_container: $("#recent_topics_table"),
        modifier(item) {
            return render_recent_topic_row(format_message(item));
        },
        filter: {
            // We use update_filters_view & filters_should_hide_topic to do all the
            // filtering for us, which is called using click_handlers.
            predicate(topic_data) {
                return !filters_should_hide_topic(topic_data);
            },
        },
        sort_fields: {
            stream_sort,
            topic_sort,
        },
        html_selector: get_topic_row,
        $simplebar_container: $("#recent_topics_table .table_fix_head"),
        callback_after_render: revive_current_focus,
        is_scroll_position_for_render,
        post_scroll__pre_render_callback: set_focus_to_element_in_center,
        get_min_load_count,
    });
}

export function show() {
    if (narrow.has_shown_message_list_view) {
        narrow.save_pre_narrow_offset_for_reload();
    }

    if (is_visible()) {
        // If we're already visible, E.g. because the user hit Esc
        // while already in the recent topics view, do nothing.
        return;
    }
    // Hide selected elements in the left sidebar.
    top_left_corner.narrow_to_recent_topics();
    stream_list.handle_narrow_deactivated();

    // Hide "middle-column" which has html for rendering
    // a messages narrow. We hide it and show recent topics.
    $("#message_feed_container").hide();
    $("#recent_topics_view").show();
    set_visible(true);
    $("#message_view_header_underpadding").hide();
    $(".header").css("padding-bottom", "0px");

    unread_ui.hide_mark_as_read_turned_off_banner();

    // We want to show `new stream message` instead of
    // `new topic`, which we are already doing in this
    // function. So, we reuse it here.
    compose_closed_ui.update_buttons_for_recent_topics();

    narrow_state.reset_current_filter();
    narrow.set_narrow_title("Recent topics");
    message_view_header.render_title_area();
    narrow.handle_middle_pane_transition();
    pm_list.handle_narrow_deactivated();

    complete_rerender();
}

function filter_buttons() {
    return $("#recent_filters_group").children();
}

export function hide() {
    // On firefox (and flaky on other browsers), focus
    // remains on the focused element even after it is hidden. We
    // forcefully blur it so that focus returns to the visible
    // focused element.
    const $focused_element = $(document.activeElement);
    if ($("#recent_topics_view").has($focused_element)) {
        $focused_element.trigger("blur");
    }

    $("#message_view_header_underpadding").show();
    $("#message_feed_container").show();
    $("#recent_topics_view").hide();
    set_visible(false);

    $(".header").css("padding-bottom", "10px");

    // This solves a bug with message_view_header
    // being broken sometimes when we narrow
    // to a filter and back to recent topics
    // before it completely re-rerenders.
    message_view_header.render_title_area();

    // Fire our custom event
    $("#message_feed_container").trigger("message_feed_shown");

    // This makes sure user lands on the selected message
    // and not always at the top of the narrow.
    navigate.plan_scroll_to_selected();
}

function is_focus_at_last_table_row() {
    const $topic_rows = $("#recent_topics_table table tbody tr");
    return row_focus === $topic_rows.length - 1;
}

function has_unread(row) {
    const last_msg_id = topics_widget.get_current_list()[row].last_msg_id;
    const last_msg = message_store.get(last_msg_id);
    return unread.num_unread_for_topic(last_msg.stream_id, last_msg.topic) > 0;
}

export function focus_clicked_element(topic_row_index, col, topic_key) {
    $current_focus_elem = "table";
    col_focus = col;
    row_focus = topic_row_index;

    if (col === COLUMNS.topic) {
        last_visited_topic = topic_key;
    }
    // Set compose_closed_ui reply button text.  The rest of the table
    // focus logic should be a noop.
    set_table_focus(row_focus, col_focus);
}

function left_arrow_navigation(row, col) {
    const type = get_row_type(row);

    if (type === "stream" && col === MAX_SELECTABLE_TOPIC_COLS - 1 && !has_unread(row)) {
        col_focus -= 1;
    }

    col_focus -= 1;
    if (col_focus < 0) {
        col_focus = get_max_selectable_cols(row) - 1;
    }
}

function right_arrow_navigation(row, col) {
    const type = get_row_type(row);

    if (type === "stream" && col === 1 && !has_unread(row)) {
        col_focus += 1;
    }

    col_focus += 1;
    if (col_focus >= get_max_selectable_cols(row)) {
        col_focus = 0;
    }
}

function up_arrow_navigation(row, col) {
    row_focus -= 1;
    if (row_focus < 0) {
        return;
    }
    const type = get_row_type(row);

    if (type === "stream" && col === 2 && row - 1 >= 0 && !has_unread(row - 1)) {
        col_focus = 1;
    }
}

function down_arrow_navigation(row, col) {
    const type = get_row_type(row);

    if (type === "stream" && col === 2 && !has_unread(row + 1)) {
        col_focus = 1;
    }
    row_focus += 1;
}

function check_row_type_transition(row, col) {
    // This function checks if the row is transitioning
    // from type "Private messages" to "Stream" or vice versa.
    // This helps in setting the col_focus as maximum column
    // of both the type are different.
    if (row < 0) {
        return false;
    }
    const max_col = get_max_selectable_cols(row);
    if (col > max_col - 1) {
        return true;
    }
    return false;
}

export function change_focused_element($elt, input_key) {
    // Called from hotkeys.js; like all logic in that module,
    // returning true will cause the caller to do
    // preventDefault/stopPropagation; false will let the browser
    // handle the key.

    if ($elt.attr("id") === "recent_topics_search") {
        // Since the search box a text area, we want the browser to handle
        // Left/Right and selection within the widget; but if the user
        // arrows off the edges, we should move focus to the adjacent widgets..
        const textInput = $("#recent_topics_search").get(0);
        const start = textInput.selectionStart;
        const end = textInput.selectionEnd;
        const text_length = textInput.value.length;
        let is_selected = false;
        if (end - start > 0) {
            is_selected = true;
        }

        switch (input_key) {
            //  Allow browser to handle all
            //  character keypresses.
            case "vim_left":
            case "vim_right":
            case "vim_down":
            case "vim_up":
            case "open_recent_topics":
                return false;
            case "shift_tab":
                $current_focus_elem = filter_buttons().last();
                break;
            case "left_arrow":
                if (start !== 0 || is_selected) {
                    return false;
                }
                $current_focus_elem = filter_buttons().last();
                break;
            case "tab":
                $current_focus_elem = filter_buttons().first();
                break;
            case "right_arrow":
                if (end !== text_length || is_selected) {
                    return false;
                }
                $current_focus_elem = filter_buttons().first();
                break;
            case "down_arrow":
                set_table_focus(row_focus, col_focus);
                return true;
            case "click":
                // Note: current_focus_elem can be different here, so we just
                // set current_focus_elem to the input box, we don't want .trigger("focus") on
                // it since it is already focused.
                // We only do this for search because we don't want the focus to
                // go away from the input box when `revive_current_focus` is called
                // on rerender when user is typing.
                $current_focus_elem = $("#recent_topics_search");
                compose_closed_ui.set_standard_text_for_reply_button();
                return true;
            case "escape":
                if (is_table_focused()) {
                    return false;
                }
                set_table_focus(row_focus, col_focus);
                return true;
        }
    } else if ($elt.hasClass("btn-recent-filters")) {
        switch (input_key) {
            case "click":
                $current_focus_elem = $elt;
                return true;
            case "shift_tab":
            case "vim_left":
            case "left_arrow":
                if (filter_buttons().first()[0] === $elt[0]) {
                    $current_focus_elem = $("#recent_topics_search");
                } else {
                    $current_focus_elem = $elt.prev();
                }
                break;
            case "tab":
            case "vim_right":
            case "right_arrow":
                if (filter_buttons().last()[0] === $elt[0]) {
                    $current_focus_elem = $("#recent_topics_search");
                } else {
                    $current_focus_elem = $elt.next();
                }
                break;
            case "vim_down":
            case "down_arrow":
                set_table_focus(row_focus, col_focus);
                return true;
            case "escape":
                if (is_table_focused()) {
                    return false;
                }
                set_table_focus(row_focus, col_focus);
                return true;
        }
    } else if (is_table_focused()) {
        // For arrowing around the table of topics, we implement left/right
        // wraparound.  Going off the top or the bottom takes one
        // to the navigation at the top (see set_table_focus).
        switch (input_key) {
            case "escape":
                return false;
            case "open_recent_topics":
                set_default_focus();
                return true;
            case "shift_tab":
            case "vim_left":
            case "left_arrow":
                left_arrow_navigation(row_focus, col_focus);
                break;
            case "tab":
            case "vim_right":
            case "right_arrow":
                right_arrow_navigation(row_focus, col_focus);
                break;
            case "vim_down":
                // We stop user at last table row
                // so that user doesn't end up in
                // input box where it is impossible to
                // get out of using vim_up / vim_down
                // keys. This also blocks the user from
                // having `jjjj` typed in the input box
                // when continuously pressing `j`.
                if (is_focus_at_last_table_row()) {
                    return true;
                }
                down_arrow_navigation(row_focus, col_focus);
                break;
            case "down_arrow":
                down_arrow_navigation(row_focus, col_focus);
                break;
            case "vim_up":
                // See comment on vim_down.
                // Similarly, blocks the user from
                // having `kkkk` typed in the input box
                // when continuously pressing `k`.
                if (row_focus === 0) {
                    return true;
                }
                up_arrow_navigation(row_focus, col_focus);
                break;
            case "up_arrow":
                up_arrow_navigation(row_focus, col_focus);
                break;
        }

        if (check_row_type_transition(row_focus, col_focus)) {
            col_focus = get_max_selectable_cols(row_focus) - 1;
        }

        set_table_focus(row_focus, col_focus, true);
        return true;
    }
    if ($current_focus_elem && input_key !== "escape") {
        $current_focus_elem.trigger("focus");
        if ($current_focus_elem.hasClass("btn-recent-filters")) {
            compose_closed_ui.set_standard_text_for_reply_button();
        }
        return true;
    }

    return false;
}
