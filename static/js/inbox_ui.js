import $ from "jquery";

import render_inbox from "../templates/inbox.hbs";
import render_inbox_list from "../templates/inbox_list.hbs";

import * as buddy_data from "./buddy_data";
import * as compose_closed_ui from "./compose_closed_ui";
import * as hash_util from "./hash_util";
import {
    correct_stream_color,
    get_pm_header_color,
    get_stream_header_color,
    is_in_focus,
    is_visible,
    set_visible,
} from "./inbox_util";
import {localstorage} from "./localstorage";
import * as message_view_header from "./message_view_header";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as navigate from "./navigate";
import * as people from "./people";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as sub_store from "./sub_store";
import * as top_left_corner from "./top_left_corner";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";
import * as util from "./util";

let pms_dict = {};
let topics_dict = {};
let streams_dict = {};
let filtered_pm_list = {};
let filtered_topic_list = {};
let unread_pms_count;
let unread_stream_msg_count;
let filter_muted = false;
let row_focus = 0;
let stream_focus = 0;

const ls_key = "inbox_mute_filter";
const ls = localstorage();

export let $current_focus_elem = "pm_header";
let last_visited_topic = "";
let last_visited_pm = "";

function save_filter() {
    ls.set(ls_key, filter_muted);
}

export function show() {
    if (narrow.has_shown_message_list_view) {
        narrow.save_pre_narrow_offset_for_reload();
    }

    if (is_visible()) {
        return;
    }

    top_left_corner.narrow_to_inbox();
    stream_list.handle_narrow_deactivated();

    $("#message_feed_container").hide();
    $("#inbox_view").show();
    set_visible(true);
    $("#message_view_header_underpadding").hide();
    $(".header").css("padding-bottom", "0px");

    unread_ui.hide_mark_as_read_turned_off_banner();
    narrow_state.reset_current_filter();
    narrow.set_narrow_title("Inbox");
    message_view_header.render_title_area();
    narrow.handle_middle_pane_transition();

    complete_rerender();
}

export function hide() {
    const $focused_element = $(document.activeElement);

    if ($("#inbox_view").has($focused_element)) {
        $focused_element.trigger("blur");
    }

    $("#message_view_header_underpadding").show();
    $("#message_feed_container").show();

    $("#inbox_view").hide();
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

function get_topic_key(stream_id, topic) {
    return stream_id + ":" + topic;
}

function get_stream_key(stream_id) {
    return "stream:" + stream_id;
}

function get_topic_row(topic_key) {
    const $topic_row = $(`#${CSS.escape("inbox:" + topic_key)}`);
    return $topic_row;
}

function get_topics_container(stream_id) {
    const $topics_container = $(`#${CSS.escape("topics:" + stream_id)}`);
    return $topics_container;
}

function get_stream_container(stream_id) {
    const $stream_container = $(`#${CSS.escape(get_stream_key(stream_id))}`);
    return $stream_container;
}

function get_header_row(stream_id) {
    const $stream_header_row = $(`#${CSS.escape("inbox_header:" + stream_id)}`);
    return $stream_header_row;
}

function compare_function(a, b) {
    const stream_a = streams_dict[a];
    const stream_b = streams_dict[b];
    const stream_name_a = stream_a ? stream_a.stream_name : "";
    const stream_name_b = stream_b ? stream_b.stream_name : "";
    return util.strcmp(stream_name_a, stream_name_b);
}

function load_filter() {
    filter_muted = ls.get(ls_key);
}

function toggle_filter() {
    const $mute_checkbox = $("#inbox_filters #inbox_filter_mute_toggle");
    if (filter_muted) {
        $mute_checkbox.removeClass("fa-square-o");
        $mute_checkbox.addClass("fa-check-square-o");
    } else {
        $mute_checkbox.removeClass("fa-check-square-o");
        $mute_checkbox.addClass("fa-square-o");
    }
}

export function set_filter() {
    const $mute_filter = $("#inbox_filters .btn-inbox-filter");
    if ($mute_filter.hasClass("btn-inbox-selected")) {
        filter_muted = false;
        $mute_filter.removeClass("btn-inbox-selected");
    } else {
        filter_muted = true;
        $mute_filter.addClass("btn-inbox-selected");
    }

    toggle_filter();
    save_filter();
    inbox_list_renderer();
}

function format_pm(user_ids_string) {
    const is_group = user_ids_string.includes(",");
    const recipients_string = people.get_recipients(user_ids_string);
    const unread_count = unread.num_unread_for_person(user_ids_string);
    const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
    let user_circle_class;

    if (!is_group) {
        const user_id = Number.parseInt(user_ids_string, 10);
        user_circle_class = buddy_data.get_user_circle_class(user_id);
        const recipient_user_obj = people.get_by_user_id(user_id);

        if (recipient_user_obj.is_bot) {
            // Bots do not have status emoji, and are modeled as
            // always present. We may want to use this space for a
            // bot icon in the future.
            user_circle_class = "user_circle_green";
        }
    }

    return {
        conversation_key: user_ids_string,
        is_private: true,
        is_group,
        pm_url: hash_util.pm_with_url(reply_to),
        recipients_string,
        user_ids_string,
        unread_count,
        user_circle_class,
    };
}

export function process_new_messages(messages) {
    for (const message of messages) {
        if (message.unread && message.type === "stream") {
            const topic = message.topic;
            const stream_id = message.stream_id;
            update_unread_count(stream_id, topic);
        }
    }
}

function format_stream(stream_id) {
    const stream_info = sub_store.get(stream_id);
    return {
        is_stream: true,
        invite_only: stream_info.invite_only,
        is_web_public: stream_info.is_web_public,
        stream_name: stream_info.name,
        stream_color: correct_stream_color(stream_info.color),
        stream_header_color: get_stream_header_color(stream_info.color),
        unread_count: unread.num_unread_for_stream(stream_id),
        stream_url: hash_util.by_stream_url(stream_id),
        stream_id,
    };
}

function format_topic(stream_id, topic) {
    const topic_unread = unread.num_unread_for_topic(stream_id, topic);
    return {
        is_topic: true,
        stream_id,
        topic_name: topic,
        unread_count: topic_unread,
        conversation_key: get_topic_key(stream_id, topic),
        topic_url: hash_util.by_stream_topic_url(stream_id, topic),
    };
}

function stream_sort(dict) {
    const sorted_stream_keys = Object.keys(dict).sort(compare_function);
    const sorted_topic_dict = {};
    for (const sorted_stream_key of sorted_stream_keys) {
        sorted_topic_dict[sorted_stream_key] = dict[sorted_stream_key];
    }

    return sorted_topic_dict;
}

export function complete_rerender() {
    if (!is_visible()) {
        return;
    }

    pms_dict = {};
    topics_dict = {};
    streams_dict = {};

    const unread_pms = unread.get_unread_pm();
    unread_pms_count = unread_pms.total_count;
    const unread_pms_dict = unread_pms.pm_dict;

    const unread_stream_message = unread.get_unread_topics();
    unread_stream_msg_count = unread_stream_message.stream_unread_messages;
    const unread_streams_dict = unread_stream_message.stream_count;

    const has_pms = unread_pms_count > 0;
    const has_topic_msgs = unread_stream_msg_count > 0;

    if (has_pms) {
        for (const [key, value] of unread_pms_dict) {
            if (value) {
                pms_dict[key] = format_pm(key);
            }
        }
    }

    if (has_topic_msgs) {
        for (const [stream_id, topic_dict] of unread_streams_dict) {
            if (unread.num_unread_for_stream(stream_id) > 0) {
                topics_dict[get_stream_key(stream_id)] = {};
                streams_dict[get_stream_key(stream_id)] = format_stream(stream_id);
                for (const [topic, topic_unread] of topic_dict) {
                    if (topic_unread) {
                        topics_dict[get_stream_key(stream_id)][get_topic_key(stream_id, topic)] =
                            format_topic(stream_id, topic);
                    }
                }
            } else {
                delete topics_dict[get_stream_key(stream_id)];
            }
        }
    }

    load_filter();
    $("#inbox_pane").html(
        render_inbox({
            search_val: $("#inbox_search").val() || "",
            filter_muted,
        }),
    );
    toggle_filter();
    inbox_list_renderer();
}

export function update_unread_count(stream_id, topic) {
    const topic_key = get_topic_key(stream_id, topic);
    const topic_unread_count = unread.num_unread_for_topic(stream_id, topic);
    const stream_unread_count = unread.num_unread_for_stream(stream_id);

    if (stream_unread_count === 0) {
        mark_stream_as_read(stream_id);
        delete topics_dict[get_stream_key(stream_id)];
        return;
    } else if (topic_unread_count === 0) {
        const $topic_row = get_topic_row(topic_key);
        $topic_row.remove();
        delete topics_dict[get_stream_key(stream_id)][get_topic_key(stream_id, topic)];
        return;
    }

    const $topic_row = get_topic_row(topic_key);
    if ($topic_row.length > 0) {
        const $stream_row = get_header_row(stream_id);
        $topic_row.find(".unread_count").text(topic_unread_count);
        $stream_row.find(".unread_count").text(stream_unread_count);
        return;
    }

    complete_rerender();
}

export function inbox_list_renderer() {
    filtered_topic_list = {};
    filtered_pm_list = {};
    const has_topic_msgs = unread_stream_msg_count > 0;
    const stream_keys = Object.keys(topics_dict);
    for (const stream_key of stream_keys) {
        const stream_id = Number.parseInt(stream_key.slice("stream:".length), 10);
        const stream_topic_dict = topics_dict[stream_key];

        filtered_topic_list[stream_key] = {};

        for (const topic_key of Object.keys(stream_topic_dict)) {
            const topic_data = stream_topic_dict[topic_key];
            const topic = topic_data.topic_name;

            if (!filter_should_hide_row({stream_id, topic})) {
                filtered_topic_list[stream_key][get_topic_key(stream_id, topic)] = topic_data;
            }
        }

        if (Object.keys(filtered_topic_list[stream_key]).length === 0) {
            delete filtered_topic_list[stream_key];
        }
    }

    const pm_keys = Object.keys(pms_dict);
    for (const pm_key of pm_keys) {
        if (!filter_should_hide_row({pm_key})) {
            filtered_pm_list[pm_key] = pms_dict[pm_key];
        }
    }

    filtered_topic_list = stream_sort(filtered_topic_list);

    const has_pms = Object.keys(filtered_pm_list).length > 0;
    const has_unread = has_topic_msgs || has_pms;

    $("#inbox_list").remove();

    $("#inbox_main").append(
        render_inbox_list({
            unread_pms_count,
            has_pms,
            has_topic_msgs,
            has_unread,
            pms_dict: filtered_pm_list,
            filtered_topic_list,
            streams_dict,
            pm_header_color: get_pm_header_color(),
        }),
    );

    revive_current_focus();
}

export function update_filters_view() {
    const search_keyword = $("#inbox_search").val() || "";

    if (search_keyword !== "") {
        inbox_list_renderer();
    }
}

function mark_stream_as_read(stream_id) {
    const $stream_container = get_stream_container(stream_id);
    $stream_container.remove();
}

function row_in_search_results(keyword, text) {
    if (keyword === "") {
        return true;
    }
    const search_words = keyword.toLowerCase().split(/\s+/);
    return search_words.every((word) => text.includes(word));
}

function filter_should_hide_row({stream_id, topic, pm_key}) {
    let text;
    if (pm_key !== undefined) {
        const recipients_string = people.get_recipients(pm_key);
        text = recipients_string.toLowerCase();
    } else {
        const sub = sub_store.get(stream_id);
        if (sub === undefined || !sub.subscribed) {
            return true;
        }
        if (!filter_muted && stream_data.is_muted(stream_id)) {
            return true;
        }
        text = (sub.name + " " + topic).toLowerCase();
    }

    const search_keyword = $("#inbox_search").val() || "";

    if (!row_in_search_results(search_keyword, text)) {
        return true;
    }

    return false;
}

export function collapse_or_expand(container_id) {
    let $toggle_icon;
    let $container;
    if (container_id === "pm_header") {
        $container = $(`#pm_container`);
        $container.toggle();
        $toggle_icon = $("#pm_header #toggle-stream-header-icon");
    } else {
        const stream_id = container_id.slice("inbox_header:".length);
        $container = get_topics_container(stream_id);
        $container.toggle();
        $toggle_icon = $(`#${CSS.escape("inbox_header:" + stream_id)} #toggle-stream-header-icon`);
    }

    if ($container.is(":visible")) {
        $toggle_icon.removeClass("fa-caret-right");
        $toggle_icon.addClass("fa-caret-down");
    } else {
        $toggle_icon.removeClass("fa-caret-down");
        $toggle_icon.addClass("fa-caret-right");
    }
}

function set_default_focus() {
    $current_focus_elem = $("#inbox_search");
    $current_focus_elem.trigger("focus");
    compose_closed_ui.set_standard_text_for_reply_button();
}

function set_pm_header_focus() {
    const $pm_header = $("#pm_header");
    setTimeout(() => $pm_header.trigger("focus"), 0);
    $current_focus_elem = "pm_header";
    return true;
}

function is_list_focused() {
    return is_pms_focused() || is_stream_header_focused() || is_topics_focused();
}

function is_pms_focused() {
    return $current_focus_elem === "pm_container";
}

function is_stream_header_focused() {
    return $current_focus_elem === "stream_header";
}

function is_topics_focused() {
    return $current_focus_elem === "stream_container";
}

function set_list_focus() {
    const pms_unread = Object.keys(filtered_pm_list).length;
    const topics_unread = Object.keys(filtered_topic_list).length;
    if (pms_unread > 0) {
        set_pm_header_focus();
        return true;
    } else if (topics_unread > 0) {
        stream_focus = 0;
        set_stream_focus(stream_focus);
        return true;
    }
    return false;
}

function set_pm_focus(row) {
    const $pm_container = $("#inbox_list #pm_container");
    const $pm_list = $pm_container.children();

    if (row >= $pm_list.length) {
        row_focus = 0;
        stream_focus = 0;
        set_stream_focus(stream_focus);
        $current_focus_elem = "stream_header";
        return true;
    } else if (row < 0) {
        row_focus = 0;
        set_pm_header_focus();
        return true;
    }

    setTimeout(() => $pm_container.children().eq(row).trigger("focus"), 0);
    $current_focus_elem = "pm_container";
    return true;
}

function set_stream_focus(stream_row) {
    const $stream_container = $("#stream_container");
    if (stream_row >= $stream_container.children().length) {
        set_default_focus();
        return true;
    } else if (stream_row < 0) {
        stream_focus = 0;
        const pms_unread = Object.keys(filtered_pm_list).length;
        if (pms_unread > 0) {
            set_pm_header_focus();
            return true;
        }
        set_default_focus();
        return true;
    }

    const $stream = $stream_container.children().eq(stream_row);
    setTimeout(() => $stream.children().eq(0).trigger("focus"), 0);
    $current_focus_elem = "stream_header";
    return true;
}

function set_topic_focus(row, stream_row) {
    const $stream_container = $("#stream_container");
    if (stream_row < 0) {
        set_stream_focus(stream_row);
        return true;
    }
    const $stream = $stream_container.children().eq(stream_row);
    const $topics_container = $stream.children().eq(1);
    const $topics_list = $topics_container.children();

    if (row >= $topics_list.length) {
        row_focus = 0;
        stream_focus += 1;
        set_stream_focus(stream_focus);
        return true;
    } else if (row < 0) {
        row_focus = 0;
        set_stream_focus(stream_focus);
        return true;
    }

    setTimeout(() => $topics_container.children().eq(row).trigger("focus"), 0);
    $current_focus_elem = "stream_container";
    return true;
}

export function focus_clicked_element($current_target) {
    const parent_container = $current_target.parent().attr("id");
    const conversation_key = $current_target.attr("id").slice("inbox:".length);

    if (parent_container === "pm_container") {
        const pm_index = $current_target.index();
        last_visited_pm = conversation_key;
        last_visited_topic = "";
        set_pm_focus(pm_index);
        return true;
    }

    const stream_id = conversation_key.split(":")[0];
    const stream_index = $current_target.closest(`#${CSS.escape("stream:" + stream_id)}`).index();
    const topic_index = $current_target.index();
    last_visited_pm = "";
    last_visited_topic = conversation_key;
    set_topic_focus(topic_index, stream_index);
    return true;
}

function revive_current_focus() {
    if (!is_in_focus()) {
        return false;
    }

    if (!$current_focus_elem) {
        set_default_focus();
        return false;
    }

    if (last_visited_topic !== "") {
        const stream_id = last_visited_topic.split(":")[0];
        const stream_index = Object.keys(filtered_topic_list).indexOf("stream:" + stream_id);
        const topic_index = Object.keys(filtered_topic_list["stream:" + stream_id]).indexOf(
            last_visited_topic,
        );
        set_topic_focus(topic_index, stream_index);
    }

    if (last_visited_pm !== "") {
        const pm_index = Object.keys(filtered_pm_list).indexOf(last_visited_pm);
        set_pm_focus(pm_index);
    }

    return true;
}

function set_filter_focus() {
    $("#filter_muted").trigger("focus");
    return true;
}

export function change_focused_element($elt, input_key) {
    if ($elt.attr("id") === "inbox_search") {
        const textInput = $("#inbox_search").get(0);
        const start = textInput.selectionStart;
        const end = textInput.selectionEnd;
        // const text_length = textInput.value.length;
        let is_selected = false;
        if (end - start > 0) {
            is_selected = true;
        }

        switch (input_key) {
            case "vim_left":
            case "vim_right":
            case "vim_down":
            case "vim_up":
                return false;
            case "down_arrow":
                set_list_focus();
                return true;
            case "right_arrow":
                if (start !== 0 || is_selected) {
                    return false;
                }
                set_filter_focus();
                break;
            case "click":
                $current_focus_elem = $("inbox_search");
                compose_closed_ui.set_standard_text_for_reply_button();
                return true;
            case "escape":
                if (is_list_focused()) {
                    return false;
                }
                set_list_focus();
                return true;
        }
    } else if ($elt.attr("id") === "filter_muted") {
        switch (input_key) {
            case "down_arrow":
                set_list_focus();
                return true;
            case "left_arrow":
            case "right_arrow":
                set_default_focus();
                return true;
        }
    } else if ($elt.attr("id") === "pm_header") {
        switch (input_key) {
            case "down_arrow":
                if (!$("#pm_container").is(":visible")) {
                    set_stream_focus(stream_focus);
                    return true;
                }
                set_pm_focus(0);
                return true;
            case "up_arrow":
                set_default_focus();
                return true;
        }
    } else if (is_pms_focused()) {
        switch (input_key) {
            case "down_arrow":
                row_focus += 1;
                set_pm_focus(row_focus);
                return true;
            case "up_arrow":
                row_focus -= 1;
                set_pm_focus(row_focus);
                return true;
        }
    } else if (is_stream_header_focused()) {
        switch (input_key) {
            case "down_arrow": {
                const stream_id = $elt.attr("id").slice("inbox_header:".length);
                const $container = get_topics_container(stream_id);
                if (!$container.is(":visible")) {
                    stream_focus += 1;
                    set_stream_focus(stream_focus);
                    return true;
                }
                set_topic_focus(0, stream_focus);
                return true;
            }
            case "up_arrow":
                stream_focus -= 1;
                set_stream_focus(stream_focus);
                $current_focus_elem = "stream_header";
                return true;
        }
    } else if (is_topics_focused()) {
        switch (input_key) {
            case "down_arrow":
                row_focus += 1;
                set_topic_focus(row_focus, stream_focus);
                return true;
            case "up_arrow":
                row_focus -= 1;
                set_topic_focus(row_focus, stream_focus);
                return true;
        }
    } else {
        set_default_focus();
    }

    return false;
}
