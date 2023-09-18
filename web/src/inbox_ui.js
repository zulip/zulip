import $ from "jquery";
import _ from "lodash";

import render_inbox_row from "../templates/inbox_view/inbox_row.hbs";
import render_inbox_stream_container from "../templates/inbox_view/inbox_stream_container.hbs";
import render_inbox_view from "../templates/inbox_view/inbox_view.hbs";

import * as buddy_data from "./buddy_data";
import * as compose_closed_ui from "./compose_closed_ui";
import * as hash_util from "./hash_util";
import {is_visible, set_visible} from "./inbox_util";
import * as keydown_util from "./keydown_util";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area";
import {localstorage} from "./localstorage";
import * as message_store from "./message_store";
import * as message_view_header from "./message_view_header";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as navigate from "./navigate";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as search from "./search";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as sub_store from "./sub_store";
import * as unread from "./unread";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import * as user_topics from "./user_topics";
import * as util from "./util";

let dms_dict = {};
let topics_dict = {};
let streams_dict = {};
let update_triggered_by_user = false;

const COLUMNS = {
    COLLAPSE_BUTTON: 0,
    RECIPIENT: 1,
    UNREAD_COUNT: 2,
};
let col_focus = COLUMNS.COLLAPSE_BUTTON;
let row_focus = 0;

const ls_filter_key = "inbox_filters";
const ls_collapsed_containers_key = "inbox_collapsed_containers";

const ls = localstorage();
let filters = new Set();
let collapsed_containers = new Set();

let search_keyword = "";
const INBOX_SEARCH_ID = "inbox-search";
const MUTED_FILTER_ID = "include_muted";
export let current_focus_id = INBOX_SEARCH_ID;

const STREAM_HEADER_PREFIX = "inbox-stream-header-";
const CONVERSATION_ID_PREFIX = "inbox-row-conversation-";

function get_row_from_conversation_key(key) {
    return $(`#${CONVERSATION_ID_PREFIX}` + CSS.escape(`${key}`));
}

function save_data_to_ls() {
    ls.set(ls_filter_key, [...filters]);
    ls.set(ls_collapsed_containers_key, [...collapsed_containers]);
}

function should_include_muted() {
    return filters.has(MUTED_FILTER_ID);
}

export function show() {
    // hashchange library is expected to hide other views.
    if (narrow.has_shown_message_list_view) {
        narrow.save_pre_narrow_offset_for_reload();
    }

    if (is_visible()) {
        return;
    }

    left_sidebar_navigation_area.highlight_inbox_view();
    stream_list.handle_narrow_deactivated();

    $("#message_feed_container").hide();
    $("#inbox-view").show();
    set_visible(true);

    unread_ui.hide_unread_banner();
    narrow_state.reset_current_filter();
    message_view_header.render_title_area();
    narrow.handle_middle_pane_transition();

    narrow_state.reset_current_filter();
    narrow.update_narrow_title(narrow_state.filter());
    message_view_header.render_title_area();
    pm_list.handle_narrow_deactivated();
    search.clear_search_form();
    complete_rerender();
    compose_closed_ui.set_standard_text_for_reply_button();
}

export function hide() {
    const $focused_element = $(document.activeElement);

    if ($("#inbox-view").has($focused_element)) {
        $focused_element.trigger("blur");
    }

    $("#message_feed_container").show();
    $("#inbox-view").hide();
    set_visible(false);

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
    return "stream_" + stream_id;
}

function get_stream_container(stream_key) {
    return $(`#${CSS.escape(stream_key)}`);
}

function get_topics_container(stream_id) {
    const $topics_container = get_stream_header_row(stream_id)
        .next(".inbox-topic-container")
        .expectOne();
    return $topics_container;
}

function get_stream_header_row(stream_id) {
    const $stream_header_row = $(`#${CSS.escape(STREAM_HEADER_PREFIX + stream_id)}`);
    return $stream_header_row;
}

function load_data_from_ls() {
    filters = new Set(ls.get(ls_filter_key));
    collapsed_containers = new Set(ls.get(ls_collapsed_containers_key));
    update_filters();
}

function update_filters() {
    const $mute_checkbox = $("#inbox-filters #inbox_filter_mute_toggle");
    const $mute_filter = $("#inbox-filters .btn-inbox-filter");
    if (should_include_muted()) {
        $mute_checkbox.removeClass("fa-square-o");
        $mute_checkbox.addClass("fa-check-square-o");
        $mute_filter.addClass("btn-inbox-selected");
    } else {
        $mute_checkbox.removeClass("fa-check-square-o");
        $mute_checkbox.addClass("fa-square-o");
        $mute_filter.removeClass("btn-inbox-selected");
    }
}

export function toggle_muted_filter() {
    const $mute_filter = $("#inbox-filters .btn-inbox-filter");
    if ($mute_filter.hasClass("btn-inbox-selected")) {
        filters.delete(MUTED_FILTER_ID);
    } else {
        filters.add(MUTED_FILTER_ID);
    }

    update_filters();
    save_data_to_ls();
    update();
}

function format_dm(user_ids_string, unread_count) {
    const recipient_ids = people.user_ids_string_to_ids_array(user_ids_string);
    if (!recipient_ids.length) {
        // Self DM
        recipient_ids.push(people.my_current_user_id());
    }

    const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
    const recipients_info = [];

    for (const user_id of recipient_ids) {
        const recipient_user_obj = people.get_by_user_id(user_id);
        if (!recipient_user_obj.is_bot) {
            const user_circle_class = buddy_data.get_user_circle_class(user_id);
            recipient_user_obj.user_circle_class = user_circle_class;
        }
        recipients_info.push(recipient_user_obj);
    }
    const context = {
        conversation_key: user_ids_string,
        is_direct: true,
        recipients_info,
        dm_url: hash_util.pm_with_url(reply_to),
        user_ids_string,
        unread_count,
        is_hidden: filter_should_hide_row({dm_key: user_ids_string}),
        is_collapsed: collapsed_containers.has("inbox-dm-header"),
    };

    return context;
}

function rerender_dm_inbox_row_if_needed(new_dm_data, old_dm_data) {
    if (old_dm_data === undefined) {
        // This row is not rendered yet.
        $("#inbox-direct-messages-container").append(render_inbox_row(new_dm_data));
        return;
    }

    for (const property in new_dm_data) {
        if (new_dm_data[property] !== old_dm_data[property]) {
            const $rendered_row = get_row_from_conversation_key(new_dm_data.conversation_key);
            $rendered_row.replaceWith(render_inbox_row(new_dm_data));
            return;
        }
    }
}

function format_stream(stream_id, unread_count_info) {
    const stream_info = sub_store.get(stream_id);
    let unread_count = unread_count_info.unmuted_count;
    if (should_include_muted()) {
        unread_count += unread_count_info.muted_count;
    }

    return {
        is_stream: true,
        invite_only: stream_info.invite_only,
        is_web_public: stream_info.is_web_public,
        stream_name: stream_info.name,
        pin_to_top: stream_info.pin_to_top,
        stream_color: stream_color.get_stream_privacy_icon_color(stream_info.color),
        stream_header_color: stream_color.get_recipient_bar_color(stream_info.color),
        unread_count,
        stream_url: hash_util.by_stream_url(stream_id),
        stream_id,
        // Will be displayed if any topic is visible.
        is_hidden: true,
        is_collapsed: collapsed_containers.has(STREAM_HEADER_PREFIX + stream_id),
    };
}

function rerender_stream_inbox_header_if_needed(new_stream_data, old_stream_data) {
    for (const property in new_stream_data) {
        if (new_stream_data[property] !== old_stream_data[property]) {
            const $rendered_row = get_stream_header_row(new_stream_data.stream_id);
            $rendered_row.replaceWith(render_inbox_row(new_stream_data));
            return;
        }
    }
}

function format_topic(stream_id, topic, topic_unread_count) {
    const context = {
        is_topic: true,
        stream_id,
        topic_name: topic,
        unread_count: topic_unread_count,
        conversation_key: get_topic_key(stream_id, topic),
        topic_url: hash_util.by_stream_topic_url(stream_id, topic),
        is_hidden: filter_should_hide_row({stream_id, topic}),
        is_collapsed: collapsed_containers.has(STREAM_HEADER_PREFIX + stream_id),
    };

    return context;
}

function insert_stream(stream_id, topic_dict, stream_unread) {
    const stream_data = format_stream(stream_id, stream_unread);
    const stream_key = get_stream_key(stream_id);
    topics_dict[stream_key] = {};
    for (const [topic, topic_unread_count] of topic_dict) {
        const topic_key = get_topic_key(stream_id, topic);
        if (topic_unread_count) {
            const topic_data = format_topic(stream_id, topic, topic_unread_count);
            topics_dict[stream_key][topic_key] = topic_data;
            if (!topic_data.is_hidden) {
                stream_data.is_hidden = false;
            }
        }
    }

    streams_dict[stream_key] = stream_data;

    const sorted_stream_keys = get_sorted_stream_keys();
    const stream_index = sorted_stream_keys.indexOf(stream_key);
    const rendered_stream = render_inbox_stream_container({
        topics_dict: {
            [stream_key]: topics_dict[stream_key],
        },
        streams_dict,
    });

    if (stream_index === 0) {
        $("#inbox-streams-container").prepend(rendered_stream);
    } else {
        const previous_stream_key = sorted_stream_keys[stream_index - 1];
        $(rendered_stream).insertAfter(get_stream_container(previous_stream_key));
    }
    return get_stream_container(stream_key);
}

function rerender_topic_inbox_row_if_needed(new_topic_data, old_topic_data) {
    // This row is not rendered yet.
    if (old_topic_data === undefined) {
        const stream_key = get_stream_key(new_topic_data.stream_id);
        const $topic_container = get_stream_container(stream_key).find(".inbox-topic-container");
        $topic_container.prepend(render_inbox_row(new_topic_data));
        return;
    }

    for (const property in new_topic_data) {
        if (new_topic_data[property] !== old_topic_data[property]) {
            const $rendered_row = get_row_from_conversation_key(new_topic_data.conversation_key);
            $rendered_row.replaceWith(render_inbox_row(new_topic_data));
            return;
        }
    }
}

function get_sorted_stream_keys() {
    function compare_function(a, b) {
        const stream_a = streams_dict[a];
        const stream_b = streams_dict[b];

        // If one of the streams is pinned, they are sorted higher.
        if (stream_a.pin_to_top && !stream_b.pin_to_top) {
            return -1;
        }

        if (stream_b.pin_to_top && !stream_a.pin_to_top) {
            return 1;
        }

        const stream_name_a = stream_a ? stream_a.stream_name : "";
        const stream_name_b = stream_b ? stream_b.stream_name : "";
        return util.strcmp(stream_name_a, stream_name_b);
    }

    return Object.keys(topics_dict).sort(compare_function);
}

function get_sorted_stream_topic_dict() {
    const sorted_stream_keys = get_sorted_stream_keys();
    const sorted_topic_dict = {};
    for (const sorted_stream_key of sorted_stream_keys) {
        sorted_topic_dict[sorted_stream_key] = topics_dict[sorted_stream_key];
    }

    return sorted_topic_dict;
}

function reset_data() {
    dms_dict = {};
    topics_dict = {};
    streams_dict = {};

    const unread_dms = unread.get_unread_pm();
    const unread_dms_count = unread_dms.total_count;
    const unread_dms_dict = unread_dms.pm_dict;

    const unread_stream_message = unread.get_unread_topics();
    const unread_stream_msg_count = unread_stream_message.stream_unread_messages;
    const unread_streams_dict = unread_stream_message.stream_count;

    let has_dms_post_filter = false;
    if (unread_dms_count) {
        for (const [key, value] of unread_dms_dict) {
            if (value) {
                const dm_data = format_dm(key, value);
                dms_dict[key] = dm_data;
                if (!dm_data.is_hidden) {
                    has_dms_post_filter = true;
                }
            }
        }
    }

    let has_topics_post_filter = false;
    if (unread_stream_msg_count) {
        for (const [stream_id, topic_dict] of unread_streams_dict) {
            const stream_unread = unread.num_unread_for_stream(stream_id);
            const stream_unread_count = stream_unread.unmuted_count + stream_unread.muted_count;
            const stream_key = get_stream_key(stream_id);
            if (stream_unread_count > 0) {
                topics_dict[stream_key] = {};
                const stream_data = format_stream(stream_id, stream_unread);
                for (const [topic, topic_unread_count] of topic_dict) {
                    if (topic_unread_count) {
                        const topic_key = get_topic_key(stream_id, topic);
                        const topic_data = format_topic(stream_id, topic, topic_unread_count);
                        topics_dict[stream_key][topic_key] = topic_data;
                        if (!topic_data.is_hidden) {
                            stream_data.is_hidden = false;
                            has_topics_post_filter = true;
                        }
                    }
                }
                streams_dict[stream_key] = stream_data;
            } else {
                delete topics_dict[stream_key];
            }
        }
    }

    const has_visible_unreads = has_dms_post_filter || has_topics_post_filter;
    topics_dict = get_sorted_stream_topic_dict();
    const is_dms_collaped = collapsed_containers.has("inbox-dm-header");

    return {
        unread_dms_count,
        is_dms_collaped,
        has_dms_post_filter,
        has_visible_unreads,
    };
}

function show_empty_inbox_text(has_visible_unreads) {
    if (!has_visible_unreads) {
        $("#inbox-list").css("border-width", 0);
        if (search_keyword) {
            $("#inbox-empty-with-search").show();
            $("#inbox-empty-without-search").hide();
        } else {
            $("#inbox-empty-with-search").hide();
            $("#inbox-empty-without-search").show();
        }
    } else {
        $(".inbox-empty-text").hide();
        $("#inbox-list").css("border-width", "1px");
    }
}

export function complete_rerender() {
    if (!is_visible()) {
        return;
    }
    load_data_from_ls();
    const {has_visible_unreads, ...additional_context} = reset_data();
    $("#inbox-pane").html(
        render_inbox_view({
            search_val: search_keyword,
            include_muted: should_include_muted(),
            INBOX_SEARCH_ID,
            MUTED_FILTER_ID,
            dms_dict,
            topics_dict,
            streams_dict,
            ...additional_context,
        }),
    );
    update_filters();
    show_empty_inbox_text(has_visible_unreads);

    setTimeout(() => {
        // We don't want to focus on simplebar ever.
        $("#inbox-list .simplebar-content-wrapper").attr("tabindex", "-1");
        revive_current_focus();
    }, 0);
}

export function search_and_update() {
    const new_keyword = $("#inbox-search").val() || "";
    if (new_keyword === search_keyword) {
        return;
    }
    search_keyword = new_keyword;
    current_focus_id = INBOX_SEARCH_ID;
    update_triggered_by_user = true;
    update();
}

function row_in_search_results(keyword, text) {
    if (keyword === "") {
        return true;
    }
    const search_words = keyword.toLowerCase().split(/\s+/);
    return search_words.every((word) => text.includes(word));
}

function filter_should_hide_row({stream_id, topic, dm_key}) {
    let text;
    if (dm_key !== undefined) {
        const recipients_string = people.get_recipients(dm_key);
        text = recipients_string.toLowerCase();
    } else {
        const sub = sub_store.get(stream_id);
        if (sub === undefined || !sub.subscribed) {
            return true;
        }

        if (user_topics.is_topic_unmuted_or_followed(stream_id, topic)) {
            return false;
        }

        if (
            !should_include_muted() &&
            (stream_data.is_muted(stream_id) || user_topics.is_topic_muted(stream_id, topic))
        ) {
            return true;
        }
        text = (sub.name + " " + topic).toLowerCase();
    }

    if (!row_in_search_results(search_keyword, text)) {
        return true;
    }

    return false;
}

export function collapse_or_expand(container_id) {
    let $toggle_icon;
    let $container;
    if (container_id === "inbox-dm-header") {
        $container = $(`#inbox-direct-messages-container`);
        $container.children().toggleClass("collapsed_container");
        $toggle_icon = $("#inbox-dm-header .toggle-inbox-header-icon");
    } else {
        const stream_id = container_id.slice(STREAM_HEADER_PREFIX.length);
        $container = get_topics_container(stream_id);
        $container.children().toggleClass("collapsed_container");
        $toggle_icon = $(
            `#${CSS.escape(STREAM_HEADER_PREFIX + stream_id)} .toggle-inbox-header-icon`,
        );
    }
    $toggle_icon.toggleClass("icon-collapsed-state");

    if (collapsed_containers.has(container_id)) {
        collapsed_containers.delete(container_id);
    } else {
        collapsed_containers.add(container_id);
    }

    save_data_to_ls();
}

function focus_current_id() {
    $(`#${current_focus_id}`).trigger("focus");
}

function set_default_focus() {
    current_focus_id = INBOX_SEARCH_ID;
    focus_current_id();
}

function is_list_focused() {
    return ![INBOX_SEARCH_ID, MUTED_FILTER_ID].includes(current_focus_id);
}

function get_all_rows() {
    return $(".inbox-header, .inbox-row").not(".hidden_by_filters, .collapsed_container");
}

function get_row_index($elt) {
    const $all_rows = get_all_rows();
    const $row = $elt.closest(".inbox-row, .inbox-header");
    return $all_rows.index($row);
}

function focus_clicked_element($elt) {
    row_focus = get_row_index($elt);
    update_triggered_by_user = true;
}

function revive_current_focus() {
    if (is_list_focused()) {
        set_list_focus();
    } else {
        focus_current_id();
    }
}

function is_row_a_header($row) {
    return $row.hasClass("inbox-header");
}

function set_list_focus(input_key) {
    const $all_rows = get_all_rows();
    const max_row_focus = $all_rows.length - 1;
    if (max_row_focus < 0) {
        set_default_focus();
        return;
    }

    if (row_focus > max_row_focus) {
        row_focus = max_row_focus;
    } else if (row_focus < 0) {
        row_focus = 0;
    }

    const $row_to_focus = $($all_rows.get(row_focus));
    current_focus_id = $row_to_focus.attr("id");
    const not_a_header_row = !is_row_a_header($row_to_focus);

    if (col_focus > COLUMNS.UNREAD_COUNT) {
        col_focus = COLUMNS.COLLAPSE_BUTTON;
    } else if (col_focus < COLUMNS.COLLAPSE_BUTTON) {
        col_focus = COLUMNS.UNREAD_COUNT;
    }

    // Since header rows always have a collapse button, other rows have one less element to focus.
    if (col_focus === COLUMNS.COLLAPSE_BUTTON) {
        if (not_a_header_row && ["left_arrow", "shift_tab"].includes(input_key)) {
            // Focus on unread count.
            col_focus = COLUMNS.UNREAD_COUNT;
        } else {
            $row_to_focus.trigger("focus");
            return;
        }
    } else if (not_a_header_row && col_focus === COLUMNS.RECIPIENT) {
        if (["right_arrow", "tab"].includes(input_key)) {
            // Focus on unread count.
            col_focus = COLUMNS.UNREAD_COUNT;
        } else if (["left_arrow", "shift_tab"].includes(input_key)) {
            col_focus = COLUMNS.COLLAPSE_BUTTON;
            $row_to_focus.trigger("focus");
            return;
        } else {
            $row_to_focus.trigger("focus");
            return;
        }
    }

    const $cols_to_focus = $row_to_focus.find("[tabindex=0]");
    $($cols_to_focus.get(col_focus - 1)).trigger("focus");
}

function focus_muted_filter() {
    current_focus_id = MUTED_FILTER_ID;
    focus_current_id();
}

function is_search_focused() {
    return current_focus_id === INBOX_SEARCH_ID;
}

function is_muted_filter_focused() {
    return current_focus_id === MUTED_FILTER_ID;
}

export function change_focused_element(input_key) {
    if (is_search_focused()) {
        const textInput = $(`#${INBOX_SEARCH_ID}`).get(0);
        const start = textInput.selectionStart;
        const end = textInput.selectionEnd;
        const text_length = textInput.value.length;
        let is_selected = false;
        if (end - start > 0) {
            is_selected = true;
        }

        switch (input_key) {
            case "down_arrow":
                set_list_focus();
                return true;
            case "right_arrow":
            case "tab":
                if (end !== text_length || is_selected) {
                    return false;
                }
                focus_muted_filter();
                return true;
            case "escape":
                set_list_focus();
                return true;
            case "shift_tab":
                // Let user focus outside inbox view.
                current_focus_id = "";
                return false;
        }
    } else if (is_muted_filter_focused()) {
        switch (input_key) {
            case "down_arrow":
            case "tab":
                set_list_focus();
                return true;
            case "left_arrow":
            case "shift_tab":
                set_default_focus();
                return true;
        }
    } else {
        switch (input_key) {
            case "vim_down":
            case "down_arrow":
                row_focus += 1;
                set_list_focus();
                return true;
            case "vim_up":
            case "up_arrow":
                if (row_focus === 0) {
                    set_default_focus();
                    return true;
                }
                row_focus -= 1;
                set_list_focus();
                return true;
            case "vim_right":
            case "right_arrow":
            case "tab":
                col_focus += 1;
                set_list_focus(input_key);
                return true;
            case "vim_left":
            case "left_arrow":
            case "shift_tab":
                col_focus -= 1;
                set_list_focus(input_key);
                return true;
        }
    }

    return false;
}

export function update() {
    if (!is_visible()) {
        return;
    }

    const unread_dms = unread.get_unread_pm();
    const unread_dms_count = unread_dms.total_count;
    const unread_dms_dict = unread_dms.pm_dict;

    const unread_stream_message = unread.get_unread_topics();
    const unread_streams_dict = unread_stream_message.stream_count;

    let has_dms_post_filter = false;
    for (const [key, value] of unread_dms_dict) {
        if (value !== 0) {
            const old_dm_data = dms_dict[key];
            const new_dm_data = format_dm(key, value);
            rerender_dm_inbox_row_if_needed(new_dm_data, old_dm_data);
            dms_dict[key] = new_dm_data;
            if (!new_dm_data.is_hidden) {
                has_dms_post_filter = true;
            }
        } else {
            // If it is rendered.
            if (dms_dict[key] !== undefined) {
                delete dms_dict[key];
                get_row_from_conversation_key(key).remove();
            }
        }
    }

    const $inbox_dm_header = $("#inbox-dm-header");
    if (!has_dms_post_filter) {
        $inbox_dm_header.addClass("hidden_by_filters");
    } else {
        $inbox_dm_header.removeClass("hidden_by_filters");
        $inbox_dm_header.find(".unread_count").text(unread_dms_count);
    }

    let has_topics_post_filter = false;
    for (const [stream_id, topic_dict] of unread_streams_dict) {
        const stream_unread = unread.num_unread_for_stream(stream_id);
        const stream_unread_count = stream_unread.unmuted_count + stream_unread.muted_count;
        const stream_key = get_stream_key(stream_id);
        if (stream_unread_count > 0) {
            // Stream isn't rendered.
            if (topics_dict[stream_key] === undefined) {
                insert_stream(stream_id, topic_dict, stream_unread);
                continue;
            }

            const new_stream_data = format_stream(stream_id, stream_unread);
            for (const [topic, topic_unread_count] of topic_dict) {
                const topic_key = get_topic_key(stream_id, topic);
                if (topic_unread_count) {
                    const old_topic_data = topics_dict[stream_key][topic_key];
                    const new_topic_data = format_topic(stream_id, topic, topic_unread_count);
                    topics_dict[stream_key][topic_key] = new_topic_data;
                    rerender_topic_inbox_row_if_needed(new_topic_data, old_topic_data);
                    if (!new_topic_data.is_hidden) {
                        new_stream_data.is_hidden = false;
                        has_topics_post_filter = true;
                    }
                } else {
                    get_row_from_conversation_key(topic_key).remove();
                }
            }
            const old_stream_data = streams_dict[stream_key];
            streams_dict[stream_key] = new_stream_data;
            rerender_stream_inbox_header_if_needed(new_stream_data, old_stream_data);
        } else {
            delete topics_dict[stream_key];
            delete streams_dict[stream_key];
            get_stream_container(stream_key).remove();
        }
    }

    const has_visible_unreads = has_dms_post_filter || has_topics_post_filter;
    show_empty_inbox_text(has_visible_unreads);

    if (update_triggered_by_user) {
        setTimeout(revive_current_focus, 0);
        update_triggered_by_user = false;
    }
}

function get_focus_class_for_header() {
    let focus_class = ".collapsible-button";

    switch (col_focus) {
        case COLUMNS.RECIPIENT: {
            focus_class = ".inbox-header-name a";
            break;
        }
        case COLUMNS.UNREAD_COUNT: {
            focus_class = ".unread_count";
            break;
        }
    }

    return focus_class;
}

function get_focus_class_for_row() {
    let focus_class = ".inbox-left-part";
    if (col_focus === COLUMNS.UNREAD_COUNT) {
        focus_class = ".unread_count";
    }
    return focus_class;
}

function center_focus_if_offscreen($elt) {
    if ($elt.length === 0) {
        return;
    }

    const element_above = document.querySelector("#inbox-filters");
    const element_down = document.querySelector("#compose");
    const visible_top = element_above.getBoundingClientRect().bottom;
    const visible_bottom = element_down.getBoundingClientRect().top;

    const elt_pos = $elt[0].getBoundingClientRect();
    if (elt_pos.top >= visible_top && elt_pos.bottom <= visible_bottom) {
        // Element is visible.
        return;
    }

    // Scroll element into center if offscreen.
    $elt[0].scrollIntoView({block: "center"});
}

export function initialize() {
    $("body").on(
        "keyup",
        "#inbox-search",
        _.debounce(() => {
            search_and_update();
        }, 300),
    );

    $("body").on("keydown", ".inbox-header", (e) => {
        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
            e.stopPropagation();

            const $elt = $(e.currentTarget);
            $elt.find(get_focus_class_for_header()).trigger("click");
        }
    });

    $("body").on("click", "#inbox-list .inbox-header .collapsible-button", (e) => {
        const $elt = $(e.currentTarget);
        const container_id = $elt.parents(".inbox-header").attr("id");
        col_focus = COLUMNS.COLLAPSE_BUTTON;
        focus_clicked_element($elt);
        collapse_or_expand(container_id);
        e.stopPropagation();
    });

    $("body").on("keydown", ".inbox-row", (e) => {
        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
            e.stopPropagation();

            const $elt = $(e.currentTarget);
            $elt.find(get_focus_class_for_row()).trigger("click");
        }
    });

    $("body").on("click", "#inbox-list .inbox-row, #inbox-list .inbox-header", (e) => {
        const $elt = $(e.currentTarget);
        col_focus = COLUMNS.RECIPIENT;
        focus_clicked_element($elt);
        window.location.href = $elt.find("a").attr("href");
    });

    $("body").on("click", "#include_muted", () => {
        current_focus_id = MUTED_FILTER_ID;
        update_triggered_by_user = true;
        toggle_muted_filter();
    });

    $("body").on("click", "#inbox-list .on_hover_dm_read", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $elt = $(e.currentTarget);
        col_focus = COLUMNS.UNREAD_COUNT;
        focus_clicked_element($elt);
        const user_ids_string = $elt.attr("data-user-ids-string");
        if (user_ids_string) {
            // direct message row
            unread_ops.mark_pm_as_read(user_ids_string);
        }
    });

    $("body").on("click", "#inbox-list .on_hover_all_dms_read", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const unread_dms_msg_ids = unread.get_msg_ids_for_private();
        const unread_dms_messages = unread_dms_msg_ids.map((msg_id) => message_store.get(msg_id));
        unread_ops.notify_server_messages_read(unread_dms_messages);
        set_default_focus();
        update_triggered_by_user = true;
    });

    $("body").on("click", "#inbox-list .on_hover_topic_read", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $elt = $(e.currentTarget);
        col_focus = COLUMNS.UNREAD_COUNT;
        focus_clicked_element($elt);
        const user_ids_string = $elt.attr("data-user-ids-string");
        if (user_ids_string) {
            // direct message row
            unread_ops.mark_pm_as_read(user_ids_string);
            return;
        }
        const stream_id = Number.parseInt($elt.attr("data-stream-id"), 10);
        const topic = $elt.attr("data-topic-name");
        if (topic) {
            unread_ops.mark_topic_as_read(stream_id, topic);
        } else {
            unread_ops.mark_stream_as_read(stream_id);
        }
    });

    $("body").on("focus", ".inbox-row, .inbox-header", (e) => {
        const $elt = $(e.currentTarget);
        center_focus_if_offscreen($elt);
    });
}
