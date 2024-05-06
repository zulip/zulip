import $ from "jquery";
import _ from "lodash";

import render_inbox_row from "../templates/inbox_view/inbox_row.hbs";
import render_inbox_stream_container from "../templates/inbox_view/inbox_stream_container.hbs";
import render_inbox_view from "../templates/inbox_view/inbox_view.hbs";
import render_introduce_zulip_view_modal from "../templates/introduce_zulip_view_modal.hbs";
import render_user_with_status_icon from "../templates/user_with_status_icon.hbs";

import * as buddy_data from "./buddy_data";
import * as compose_closed_ui from "./compose_closed_ui";
import * as compose_state from "./compose_state";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import * as hash_util from "./hash_util";
import {$t_html} from "./i18n";
import {is_visible, set_visible} from "./inbox_util";
import * as keydown_util from "./keydown_util";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area";
import {localstorage} from "./localstorage";
import * as message_store from "./message_store";
import * as modals from "./modals";
import * as onboarding_steps from "./onboarding_steps";
import * as overlays from "./overlays";
import * as people from "./people";
import * as popovers from "./popovers";
import * as sidebar_ui from "./sidebar_ui";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as unread from "./unread";
import * as unread_ops from "./unread_ops";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_topics from "./user_topics";
import * as user_topics_ui from "./user_topics_ui";
import * as util from "./util";
import * as views_util from "./views_util";

let dms_dict = new Map();
let topics_dict = new Map();
let streams_dict = new Map();
let update_triggered_by_user = false;
let filters_dropdown_widget;

const COLUMNS = {
    COLLAPSE_BUTTON: 0,
    RECIPIENT: 1,
    UNREAD_COUNT: 2,
    TOPIC_VISIBILITY: 3,
    ACTION_MENU: 4,
};
let col_focus = COLUMNS.COLLAPSE_BUTTON;
let row_focus = 0;

const ls_filter_key = "inbox-filters";
const ls_collapsed_containers_key = "inbox_collapsed_containers";

const ls = localstorage();
let filters = new Set([views_util.FILTERS.UNMUTED_TOPICS]);
let collapsed_containers = new Set();

let search_keyword = "";
const INBOX_SEARCH_ID = "inbox-search";
const INBOX_FILTERS_DROPDOWN_ID = "inbox-filter_widget";
export let current_focus_id;

const STREAM_HEADER_PREFIX = "inbox-stream-header-";
const CONVERSATION_ID_PREFIX = "inbox-row-conversation-";

const LEFT_NAVIGATION_KEYS = ["left_arrow", "shift_tab", "vim_left"];
const RIGHT_NAVIGATION_KEYS = ["right_arrow", "tab", "vim_right"];

function get_row_from_conversation_key(key) {
    return $(`#${CONVERSATION_ID_PREFIX}` + CSS.escape(`${key}`));
}

function save_data_to_ls() {
    ls.set(ls_filter_key, [...filters]);
    ls.set(ls_collapsed_containers_key, [...collapsed_containers]);
}

export function show() {
    // Avoid setting col_focus to recipient when moving to inbox from other narrows.
    // We prefer to focus entire row instead of stream name for inbox-header.
    // Since inbox-row doesn't has a collapse button, focus on COLUMNS.COLLAPSE_BUTTON
    // is same as focus on COLUMNS.RECIPIENT. See `set_list_focus` for details.
    if (col_focus === COLUMNS.RECIPIENT) {
        col_focus = COLUMNS.COLLAPSE_BUTTON;
    }

    views_util.show({
        highlight_view_in_left_sidebar: left_sidebar_navigation_area.highlight_inbox_view,
        $view: $("#inbox-view"),
        update_compose: compose_closed_ui.update_buttons_for_non_specific_views,
        is_visible,
        set_visible,
        complete_rerender,
    });

    if (onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("intro_inbox_view_modal")) {
        const html_body = render_introduce_zulip_view_modal({
            zulip_view: "inbox",
            current_home_view_and_escape_navigation_enabled:
                user_settings.web_home_view === "inbox" &&
                user_settings.web_escape_navigates_to_home_view,
        });
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Welcome to your <b>inbox</b>!"}),
            html_body,
            html_submit_button: $t_html({defaultMessage: "Continue"}),
            on_click() {},
            single_footer_button: true,
            focus_submit_on_open: true,
        });
        onboarding_steps.post_onboarding_step_as_read("intro_inbox_view_modal");
    }
}

export function hide() {
    views_util.hide({
        $view: $("#inbox-view"),
        set_visible,
    });
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
    const saved_filters = new Set(ls.get(ls_filter_key));
    const valid_filters = new Set(Object.values(views_util.FILTERS));
    // If saved filters are not in the list of valid filters, we reset to default.
    const is_subset = [...saved_filters].every((filter) => valid_filters.has(filter));
    if (saved_filters.size === 0 || !is_subset) {
        filters = new Set([views_util.FILTERS.UNMUTED_TOPICS]);
    } else {
        filters = saved_filters;
    }
    collapsed_containers = new Set(ls.get(ls_collapsed_containers_key));
}

function format_dm(user_ids_string, unread_count, latest_msg_id) {
    const recipient_ids = people.user_ids_string_to_ids_array(user_ids_string);
    if (!recipient_ids.length) {
        // Self DM
        recipient_ids.push(people.my_current_user_id());
    }

    const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
    const rendered_dm_with = recipient_ids
        .map((recipient_id) => ({
            name: people.get_display_full_name(recipient_id),
            status_emoji_info: user_status.get_status_emoji(recipient_id),
        }))
        .sort((a, b) => util.strcmp(a.name, b.name))
        .map((user_info) => render_user_with_status_icon(user_info));

    let user_circle_class;
    let is_bot = false;
    if (recipient_ids.length === 1) {
        is_bot = people.get_by_user_id(recipient_ids[0]).is_bot;
        user_circle_class = is_bot ? false : buddy_data.get_user_circle_class(recipient_ids[0]);
    }

    const context = {
        conversation_key: user_ids_string,
        is_direct: true,
        rendered_dm_with: util.format_array_as_list(rendered_dm_with, "long", "conjunction"),
        is_group: recipient_ids.length > 1,
        user_circle_class,
        is_bot,
        dm_url: hash_util.pm_with_url(reply_to),
        user_ids_string,
        unread_count,
        is_hidden: filter_should_hide_row({dm_key: user_ids_string}),
        is_collapsed: collapsed_containers.has("inbox-dm-header"),
        latest_msg_id,
    };

    return context;
}

function insert_dms(keys_to_insert) {
    const sorted_keys = [...dms_dict.keys()];
    // If we need to insert at the top, we do it separately to avoid edge case in loop below.
    if (keys_to_insert.includes(sorted_keys[0])) {
        $("#inbox-direct-messages-container").prepend(
            $(render_inbox_row(dms_dict.get(sorted_keys[0]))),
        );
    }

    for (const [i, key] of sorted_keys.entries()) {
        if (i === 0) {
            continue;
        }

        if (keys_to_insert.includes(key)) {
            const $previous_row = get_row_from_conversation_key(sorted_keys[i - 1]);
            $previous_row.after($(render_inbox_row(dms_dict.get(key))));
        }
    }
}

function rerender_dm_inbox_row_if_needed(new_dm_data, old_dm_data, dm_keys_to_insert) {
    if (old_dm_data === undefined) {
        // This row is not rendered yet.
        dm_keys_to_insert.push(new_dm_data.conversation_key);
        return;
    }

    if (old_dm_data.latest_msg_id !== new_dm_data.latest_msg_id) {
        // Row's index likely changed in list, so remove it and insert again.
        get_row_from_conversation_key(new_dm_data.conversation_key).remove();
        dm_keys_to_insert.push(new_dm_data.conversation_key);
        return;
    }

    // If row's latest_msg_id didn't change, we can inplace rerender it, if needed.
    for (const property in new_dm_data) {
        if (new_dm_data[property] !== old_dm_data[property]) {
            const $rendered_row = get_row_from_conversation_key(new_dm_data.conversation_key);
            $rendered_row.replaceWith($(render_inbox_row(new_dm_data)));
            return;
        }
    }
}

function format_stream(stream_id) {
    // NOTE: Unread count is not included in this function as it is more
    // efficient for the callers to calculate it based on filters.
    const stream_info = sub_store.get(stream_id);

    return {
        is_stream: true,
        invite_only: stream_info.invite_only,
        is_web_public: stream_info.is_web_public,
        stream_name: stream_info.name,
        pin_to_top: stream_info.pin_to_top,
        is_muted: stream_info.is_muted,
        stream_color: stream_color.get_stream_privacy_icon_color(stream_info.color),
        stream_header_color: stream_color.get_recipient_bar_color(stream_info.color),
        stream_url: hash_util.by_stream_url(stream_id),
        stream_id,
        // Will be displayed if any topic is visible.
        is_hidden: true,
        is_collapsed: collapsed_containers.has(STREAM_HEADER_PREFIX + stream_id),
        mention_in_unread: unread.stream_has_any_unread_mentions(stream_id),
    };
}

function update_stream_data(stream_id, stream_key, topic_dict) {
    topics_dict.set(stream_key, new Map());
    const stream_data = format_stream(stream_id);
    let stream_post_filter_unread_count = 0;
    for (const [topic, {topic_count, latest_msg_id}] of topic_dict) {
        const topic_key = get_topic_key(stream_id, topic);
        if (topic_count) {
            const topic_data = format_topic(stream_id, topic, topic_count, latest_msg_id);
            topics_dict.get(stream_key).set(topic_key, topic_data);
            if (!topic_data.is_hidden) {
                stream_post_filter_unread_count += topic_data.unread_count;
            }
        }
    }
    topics_dict.set(stream_key, get_sorted_row_dict(topics_dict.get(stream_key)));
    stream_data.is_hidden = stream_post_filter_unread_count === 0;
    stream_data.unread_count = stream_post_filter_unread_count;
    streams_dict.set(stream_key, stream_data);
}

function rerender_stream_inbox_header_if_needed(new_stream_data, old_stream_data) {
    for (const property in new_stream_data) {
        if (new_stream_data[property] !== old_stream_data[property]) {
            const $rendered_row = get_stream_header_row(new_stream_data.stream_id);
            $rendered_row.replaceWith($(render_inbox_row(new_stream_data)));
            return;
        }
    }
}

function format_topic(stream_id, topic, topic_unread_count, latest_msg_id) {
    const context = {
        is_topic: true,
        stream_id,
        topic_name: topic,
        unread_count: topic_unread_count,
        conversation_key: get_topic_key(stream_id, topic),
        topic_url: hash_util.by_stream_topic_url(stream_id, topic),
        is_hidden: filter_should_hide_row({stream_id, topic}),
        is_collapsed: collapsed_containers.has(STREAM_HEADER_PREFIX + stream_id),
        mention_in_unread: unread.topic_has_any_unread_mentions(stream_id, topic),
        latest_msg_id,
        // The 'all_visibility_policies' field is not specific to this context,
        // but this is the easiest way we've figured out for passing the data
        // to the template rendering.
        all_visibility_policies: user_topics.all_visibility_policies,
        visibility_policy: user_topics.get_topic_visibility_policy(stream_id, topic),
    };

    return context;
}

function insert_stream(stream_id, topic_dict) {
    const stream_key = get_stream_key(stream_id);
    update_stream_data(stream_id, stream_key, topic_dict);
    const sorted_stream_keys = get_sorted_stream_keys();
    const stream_index = sorted_stream_keys.indexOf(stream_key);
    const rendered_stream = render_inbox_stream_container({
        topics_dict: new Map([[stream_key, topics_dict.get(stream_key)]]),
        streams_dict,
    });

    if (stream_index === 0) {
        $("#inbox-streams-container").prepend($(rendered_stream));
    } else {
        const previous_stream_key = sorted_stream_keys[stream_index - 1];
        $(rendered_stream).insertAfter(get_stream_container(previous_stream_key));
    }
    return !streams_dict.get(stream_key).is_hidden;
}

function insert_topics(keys, stream_key) {
    const stream_topics_data = topics_dict.get(stream_key);
    const sorted_keys = [...stream_topics_data.keys()];
    // If we need to insert at the top, we do it separately to avoid edge case in loop below.
    if (keys.includes(sorted_keys[0])) {
        const $stream = get_stream_container(stream_key);
        $stream
            .find(".inbox-topic-container")
            .prepend($(render_inbox_row(stream_topics_data.get(sorted_keys[0]))));
    }

    for (const [i, key] of sorted_keys.entries()) {
        if (i === 0) {
            continue;
        }

        if (keys.includes(key)) {
            const $previous_row = get_row_from_conversation_key(sorted_keys[i - 1]);
            $previous_row.after($(render_inbox_row(stream_topics_data.get(key))));
        }
    }
}

function rerender_topic_inbox_row_if_needed(new_topic_data, old_topic_data, topic_keys_to_insert) {
    if (old_topic_data === undefined) {
        // This row is not rendered yet.
        topic_keys_to_insert.push(new_topic_data.conversation_key);
        return;
    }

    if (old_topic_data.latest_msg_id !== new_topic_data.latest_msg_id) {
        // Row's index likely changed in list, so remove it and insert again.
        get_row_from_conversation_key(new_topic_data.conversation_key).remove();
        topic_keys_to_insert.push(new_topic_data.conversation_key);
    }

    for (const property in new_topic_data) {
        if (new_topic_data[property] !== old_topic_data[property]) {
            const $rendered_row = get_row_from_conversation_key(new_topic_data.conversation_key);
            $rendered_row.replaceWith($(render_inbox_row(new_topic_data)));
            return;
        }
    }
}

function get_sorted_stream_keys() {
    function compare_function(a, b) {
        const stream_a = streams_dict.get(a);
        const stream_b = streams_dict.get(b);

        // If one of the streams is pinned, they are sorted higher.
        if (stream_a.pin_to_top && !stream_b.pin_to_top) {
            return -1;
        }

        if (stream_b.pin_to_top && !stream_a.pin_to_top) {
            return 1;
        }

        // The muted stream is sorted lower.
        // (Both stream are either pinned or not pinned right now)
        if (stream_a.is_muted && !stream_b.is_muted) {
            return 1;
        }

        if (stream_b.is_muted && !stream_a.is_muted) {
            return -1;
        }

        const stream_name_a = stream_a ? stream_a.stream_name : "";
        const stream_name_b = stream_b ? stream_b.stream_name : "";
        return util.strcmp(stream_name_a, stream_name_b);
    }

    return [...topics_dict.keys()].sort(compare_function);
}

function get_sorted_stream_topic_dict() {
    const sorted_stream_keys = get_sorted_stream_keys();
    const sorted_topic_dict = new Map();
    for (const sorted_stream_key of sorted_stream_keys) {
        sorted_topic_dict.set(sorted_stream_key, topics_dict.get(sorted_stream_key));
    }

    return sorted_topic_dict;
}

function get_sorted_row_keys(row_dict) {
    return [...row_dict.keys()].sort(
        (a, b) => row_dict.get(b).latest_msg_id - row_dict.get(a).latest_msg_id,
    );
}

function get_sorted_row_dict(row_dict) {
    const sorted_row_keys = get_sorted_row_keys(row_dict);
    const sorted_row_dict = new Map();
    for (const row_key of sorted_row_keys) {
        sorted_row_dict.set(row_key, row_dict.get(row_key));
    }
    return sorted_row_dict;
}

function reset_data() {
    dms_dict = new Map();
    topics_dict = new Map();
    streams_dict = new Map();

    const unread_dms = unread.get_unread_pm();
    const unread_dms_count = unread_dms.total_count;
    const unread_dms_dict = unread_dms.pm_dict;

    const unread_stream_message = unread.get_unread_topics();
    const unread_stream_msg_count = unread_stream_message.stream_unread_messages;
    const unread_streams_dict = unread_stream_message.topic_counts;

    let has_dms_post_filter = false;
    if (unread_dms_count) {
        for (const [key, {count, latest_msg_id}] of unread_dms_dict) {
            if (count) {
                const dm_data = format_dm(key, count, latest_msg_id);
                dms_dict.set(key, dm_data);
                if (!dm_data.is_hidden) {
                    has_dms_post_filter = true;
                }
            }
        }
    }
    dms_dict = get_sorted_row_dict(dms_dict);

    let has_topics_post_filter = false;
    if (unread_stream_msg_count) {
        for (const [stream_id, topic_dict] of unread_streams_dict) {
            const stream_unread = unread.unread_count_info_for_stream(stream_id);
            const stream_unread_count = stream_unread.unmuted_count + stream_unread.muted_count;
            const stream_key = get_stream_key(stream_id);
            if (stream_unread_count > 0) {
                update_stream_data(stream_id, stream_key, topic_dict);
                if (!streams_dict.get(stream_key).is_hidden) {
                    has_topics_post_filter = true;
                }
            } else {
                topics_dict.delete(stream_key);
            }
        }
    }

    const has_visible_unreads = has_dms_post_filter || has_topics_post_filter;
    topics_dict = get_sorted_stream_topic_dict();
    const is_dms_collapsed = collapsed_containers.has("inbox-dm-header");

    return {
        unread_dms_count,
        is_dms_collapsed,
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
            // Use display value specified in CSS.
            $("#inbox-empty-without-search").css("display", "");
        }
    } else {
        $(".inbox-empty-text").hide();
        $("#inbox-list").css("border-width", "1px");
    }
}

function filter_click_handler(event, dropdown, widget) {
    event.preventDefault();
    event.stopPropagation();

    const filter_id = $(event.currentTarget).attr("data-unique-id");
    // We don't support multiple filters yet, so we clear existing and add the new filter.
    filters = new Set([filter_id]);
    save_data_to_ls();
    dropdown.hide();
    widget.render();
    update();
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
            INBOX_SEARCH_ID,
            dms_dict,
            topics_dict,
            streams_dict,
            ...additional_context,
        }),
    );
    show_empty_inbox_text(has_visible_unreads);
    // If the focus is not on the inbox rows, the inbox view scrolls
    // down when moving from other views to the inbox view. To avoid
    // this, we scroll to top before restoring focus via revive_current_focus.
    $("html").scrollTop(0);
    setTimeout(() => {
        // We don't want to focus on simplebar ever.
        $("#inbox-list .simplebar-content-wrapper").attr("tabindex", "-1");
        revive_current_focus();
    }, 0);

    filters_dropdown_widget = new dropdown_widget.DropdownWidget({
        ...views_util.COMMON_DROPDOWN_WIDGET_PARAMS,
        widget_name: "inbox-filter",
        item_click_callback: filter_click_handler,
        $events_container: $("#inbox-main"),
        default_id: filters.values().next().value,
    });
    filters_dropdown_widget.setup();
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

        if (
            filters.has(views_util.FILTERS.FOLLOWED_TOPICS) &&
            !user_topics.is_topic_followed(stream_id, topic)
        ) {
            return true;
        }

        if (
            filters.has(views_util.FILTERS.UNMUTED_TOPICS) &&
            (user_topics.is_topic_muted(stream_id, topic) || stream_data.is_muted(stream_id)) &&
            !user_topics.is_topic_unmuted_or_followed(stream_id, topic)
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

function focus_inbox_search() {
    current_focus_id = INBOX_SEARCH_ID;
    focus_current_id();
}

function is_list_focused() {
    return ![INBOX_SEARCH_ID, INBOX_FILTERS_DROPDOWN_ID].includes(current_focus_id);
}

function get_all_rows() {
    return $(".inbox-header, .inbox-row").not(".hidden_by_filters, .collapsed_container");
}

function get_row_index($elt) {
    const $all_rows = get_all_rows();
    const $row = $elt.closest(".inbox-row, .inbox-header");
    return $all_rows.index($row);
}

function focus_clicked_list_element($elt) {
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

function update_closed_compose_text($row, is_header_row) {
    // TODO: This fake "message" object is designed to allow using the
    // get_recipient_label helper inside compose_closed_ui. Surely
    // there's a more readable way to write this code.
    // Similar code is present in recent view.

    if (is_header_row) {
        compose_closed_ui.set_standard_text_for_reply_button();
        return;
    }

    let message;
    const is_dm = $row.parent("#inbox-direct-messages-container").length > 0;
    if (is_dm) {
        message = {
            display_reply_to: $row.find(".recipients_name").text(),
        };
    } else {
        const $stream = $row.parent(".inbox-topic-container").prev(".inbox-header");
        message = {
            stream_id: Number.parseInt($stream.attr("data-stream-id"), 10),
            topic: $row.find(".inbox-topic-name a").text(),
        };
    }
    compose_closed_ui.update_reply_recipient_label(message);
}

export function get_focused_row_message() {
    if (!is_list_focused()) {
        return {message: undefined};
    }

    const $all_rows = get_all_rows();
    const $focused_row = $($all_rows.get(row_focus));
    if (is_row_a_header($focused_row)) {
        const is_dm_header = $focused_row.attr("id") === "inbox-dm-header";
        if (is_dm_header) {
            return {message: undefined, msg_type: "private"};
        }

        const stream_id = Number.parseInt($focused_row.attr("data-stream-id"), 10);
        compose_state.set_compose_recipient_id(stream_id);
        return {message: undefined, msg_type: "stream", stream_id};
    }

    const is_dm = $focused_row.parent("#inbox-direct-messages-container").length > 0;
    const conversation_key = $focused_row.attr("id").slice(CONVERSATION_ID_PREFIX.length);
    let row_info;
    if (is_dm) {
        row_info = dms_dict.get(conversation_key);
    } else {
        const $stream = $focused_row.parent(".inbox-topic-container").parent();
        const stream_key = $stream.attr("id");
        row_info = topics_dict.get(stream_key).get(conversation_key);
    }

    const message = message_store.get(row_info.latest_msg_id);
    // Since inbox is populated based on unread data which is part
    // of /register request, it is possible that we don't have the
    // actual message in our message_store. In that case, we return
    // a fake message object.
    if (message === undefined) {
        if (is_dm) {
            const recipients = people.user_ids_string_to_emails_string(row_info.user_ids_string);
            return {
                msg_type: "private",
                private_message_recipient: recipients,
            };
        }
        return {
            msg_type: "stream",
            stream_id: row_info.stream_id,
            topic: row_info.topic_name,
        };
    }

    return {message};
}

export function toggle_topic_visibility_policy() {
    const inbox_message = get_focused_row_message();
    if (inbox_message.message !== undefined) {
        user_topics_ui.toggle_topic_visibility_policy(inbox_message.message);
        if (inbox_message.message.type === "stream") {
            // means mute/unmute action is taken
            const $elt = $(".inbox-header"); // Select the element with class "inbox-header"
            const $focusElement = $elt.find(get_focus_class_for_header()).first();
            focus_clicked_list_element($focusElement);
            return true;
        }
    }
    return false;
}

function is_row_a_header($row) {
    return $row.hasClass("inbox-header");
}

function set_list_focus(input_key) {
    // This function is used for both revive_current_focus and
    // setting focus after modify col_focus and row_focus as per
    // hotkey pressed by user.
    //
    // When to focus on entire row?
    // For `inbox-header`, when focus on COLUMNS.COLLAPSE_BUTTON
    // For `inbox-row`, when focus on COLUMNS.COLLAPSE_BUTTON (fake) or COLUMNS.RECIPIENT

    const $all_rows = get_all_rows();
    const max_row_focus = $all_rows.length - 1;
    if (max_row_focus < 0) {
        focus_filters_dropdown();
        return;
    }

    if (row_focus > max_row_focus) {
        row_focus = max_row_focus;
    } else if (row_focus < 0) {
        row_focus = 0;
    }

    const $row_to_focus = $($all_rows.get(row_focus));
    // This includes a fake collapse button for `inbox-row` and a fake topic visibility
    // button for `inbox-header`. The fake buttons help simplify code here and
    // `$($cols_to_focus[col_focus]).trigger("focus");` at the end of this function.
    const $cols_to_focus = [$row_to_focus, ...$row_to_focus.find("[tabindex=0]")];
    const total_cols = $cols_to_focus.length;
    current_focus_id = $row_to_focus.attr("id");
    const is_header_row = is_row_a_header($row_to_focus);
    update_closed_compose_text($row_to_focus, is_header_row);

    // Loop through columns.
    if (col_focus > total_cols - 1) {
        col_focus = 0;
    } else if (col_focus < 0) {
        col_focus = total_cols - 1;
    }

    // Since header rows always have a collapse button, other rows have one less element to focus.
    if (col_focus === COLUMNS.COLLAPSE_BUTTON) {
        if (!is_header_row && LEFT_NAVIGATION_KEYS.includes(input_key)) {
            // In `inbox-row` user pressed left on COLUMNS.RECIPIENT, so
            // go to the last column.
            col_focus = total_cols - 1;
        }
    } else if (!is_header_row && col_focus === COLUMNS.RECIPIENT) {
        if (RIGHT_NAVIGATION_KEYS.includes(input_key)) {
            // In `inbox-row` user pressed right on COLUMNS.COLLAPSE_BUTTON.
            // Since `inbox-row` has no collapse button, user wants to go
            // to the unread count button.
            col_focus = COLUMNS.UNREAD_COUNT;
        } else if (LEFT_NAVIGATION_KEYS.includes(input_key)) {
            // In `inbox-row` user pressed left on COLUMNS.UNREAD_COUNT,
            // we move focus to COLUMNS.COLLAPSE_BUTTON so that moving
            // up or down to `inbox-header` keeps the entire row focused for the
            // `inbox-header` too.
            col_focus = COLUMNS.COLLAPSE_BUTTON;
        } else {
            // up / down arrow
            // For `inbox-row`, we focus entire row for COLUMNS.RECIPIENT.
            $row_to_focus.trigger("focus");
            return;
        }
    } else if (is_header_row && col_focus === COLUMNS.TOPIC_VISIBILITY) {
        // `inbox-header` doesn't have a topic visibility indicator, so focus on
        // button around it instead.
        if (LEFT_NAVIGATION_KEYS.includes(input_key)) {
            col_focus = COLUMNS.UNREAD_COUNT;
        } else {
            col_focus = COLUMNS.ACTION_MENU;
        }
    }

    $($cols_to_focus[col_focus]).trigger("focus");
}

function focus_filters_dropdown() {
    current_focus_id = INBOX_FILTERS_DROPDOWN_ID;
    $(`#${INBOX_FILTERS_DROPDOWN_ID}`).trigger("focus");
}

function is_search_focused() {
    return current_focus_id === INBOX_SEARCH_ID;
}

function is_filters_dropdown_focused() {
    return current_focus_id === INBOX_FILTERS_DROPDOWN_ID;
}

function get_page_up_down_delta() {
    const element_above = document.querySelector("#inbox-filters");
    const element_down = document.querySelector("#compose");
    const visible_top = element_above.getBoundingClientRect().bottom;
    const visible_bottom = element_down.getBoundingClientRect().top;
    // One usually wants PageDown to move what had been the bottom row
    // to now be at the top, so one can be confident one will see
    // every row using it. This offset helps achieve that goal.
    //
    // See navigate.amount_to_paginate for similar logic in the message feed.
    const scrolling_reduction_to_maintain_context = 30;

    const delta = visible_bottom - visible_top - scrolling_reduction_to_maintain_context;
    return delta;
}

function page_up_navigation() {
    const delta = get_page_up_down_delta();
    const scroll_element = document.documentElement;
    const new_scrollTop = scroll_element.scrollTop - delta;
    if (new_scrollTop <= 0) {
        row_focus = 0;
    }
    scroll_element.scrollTop = new_scrollTop;
    set_list_focus();
}

function page_down_navigation() {
    const delta = get_page_up_down_delta();
    const scroll_element = document.documentElement;
    const new_scrollTop = scroll_element.scrollTop + delta;
    const $all_rows = get_all_rows();
    const $last_row = $all_rows.last();
    const last_row_bottom = $last_row.offset().top + $last_row.outerHeight();
    // Move focus to last row if it is visible and we are at the bottom.
    if (last_row_bottom <= new_scrollTop) {
        row_focus = get_all_rows().length - 1;
    }
    scroll_element.scrollTop = new_scrollTop;
    set_list_focus();
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
            case "tab":
                set_list_focus();
                return true;
            case "right_arrow":
                if (end !== text_length || is_selected) {
                    return false;
                }
                focus_filters_dropdown();
                return true;
            case "left_arrow":
                if (start !== 0 || is_selected) {
                    return false;
                }
                focus_filters_dropdown();
                return true;
            case "escape":
                if (get_all_rows().length === 0) {
                    return false;
                }
                set_list_focus();
                return true;
        }
    } else if (is_filters_dropdown_focused()) {
        switch (input_key) {
            case "vim_down":
            case "down_arrow":
                set_list_focus();
                return true;
            case "vim_left":
            case "left_arrow":
                focus_inbox_search();
                return true;
            case "vim_right":
            case "right_arrow":
            case "tab":
                focus_inbox_search();
                return true;
            case "shift_tab":
                // Let user focus outside inbox view.
                current_focus_id = "";
                return false;
            case "escape":
                if (get_all_rows().length === 0) {
                    return false;
                }
                set_list_focus();
                return true;
        }
    } else {
        switch (input_key) {
            case "vim_down":
            case "down_arrow":
                row_focus += 1;
                set_list_focus();
                center_focus_if_offscreen();
                return true;
            case "vim_up":
            case "up_arrow":
                if (row_focus === 0) {
                    focus_filters_dropdown();
                    return true;
                }
                row_focus -= 1;
                set_list_focus();
                center_focus_if_offscreen();
                return true;
            case RIGHT_NAVIGATION_KEYS[0]:
            case RIGHT_NAVIGATION_KEYS[1]:
            case RIGHT_NAVIGATION_KEYS[2]:
                col_focus += 1;
                set_list_focus(input_key);
                return true;
            case LEFT_NAVIGATION_KEYS[0]:
            case LEFT_NAVIGATION_KEYS[1]:
            case LEFT_NAVIGATION_KEYS[2]:
                col_focus -= 1;
                set_list_focus(input_key);
                return true;
            case "page_up":
                page_up_navigation();
                return true;
            case "page_down":
                page_down_navigation();
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
    const unread_streams_dict = unread_stream_message.topic_counts;

    let has_dms_post_filter = false;
    const dm_keys_to_insert = [];
    for (const [key, {count, latest_msg_id}] of unread_dms_dict) {
        if (count !== 0) {
            const old_dm_data = dms_dict.get(key);
            const new_dm_data = format_dm(key, count, latest_msg_id);
            rerender_dm_inbox_row_if_needed(new_dm_data, old_dm_data, dm_keys_to_insert);
            dms_dict.set(key, new_dm_data);
            if (!new_dm_data.is_hidden) {
                has_dms_post_filter = true;
            }
        } else {
            // If it is rendered.
            if (dms_dict.get(key) !== undefined) {
                dms_dict.delete(key);
                get_row_from_conversation_key(key).remove();
            }
        }
    }

    dms_dict = get_sorted_row_dict(dms_dict);
    insert_dms(dm_keys_to_insert);

    const $inbox_dm_header = $("#inbox-dm-header");
    if (!has_dms_post_filter) {
        $inbox_dm_header.addClass("hidden_by_filters");
    } else {
        $inbox_dm_header.removeClass("hidden_by_filters");
        $inbox_dm_header.find(".unread_count").text(unread_dms_count);
    }

    let has_topics_post_filter = false;
    for (const [stream_id, topic_dict] of unread_streams_dict) {
        const stream_unread = unread.unread_count_info_for_stream(stream_id);
        const stream_unread_count = stream_unread.unmuted_count + stream_unread.muted_count;
        const stream_key = get_stream_key(stream_id);
        let stream_post_filter_unread_count = 0;
        if (stream_unread_count > 0) {
            // Stream isn't rendered.
            if (topics_dict.get(stream_key) === undefined) {
                const is_stream_visible = insert_stream(stream_id, topic_dict);
                if (is_stream_visible) {
                    has_topics_post_filter = true;
                }
                continue;
            }

            const topic_keys_to_insert = [];
            const new_stream_data = format_stream(stream_id);
            for (const [topic, {topic_count, latest_msg_id}] of topic_dict) {
                const topic_key = get_topic_key(stream_id, topic);
                if (topic_count) {
                    const old_topic_data = topics_dict.get(stream_key).get(topic_key);
                    const new_topic_data = format_topic(
                        stream_id,
                        topic,
                        topic_count,
                        latest_msg_id,
                    );
                    topics_dict.get(stream_key).set(topic_key, new_topic_data);
                    rerender_topic_inbox_row_if_needed(
                        new_topic_data,
                        old_topic_data,
                        topic_keys_to_insert,
                    );
                    if (!new_topic_data.is_hidden) {
                        has_topics_post_filter = true;
                        stream_post_filter_unread_count += new_topic_data.unread_count;
                    }
                } else {
                    // Remove old topic data since it can act as false data for renamed / a new
                    // topic having the same name as old topic.
                    topics_dict.get(stream_key).delete(topic_key);
                    get_row_from_conversation_key(topic_key).remove();
                }
            }
            const old_stream_data = streams_dict.get(stream_key);
            new_stream_data.is_hidden = stream_post_filter_unread_count === 0;
            new_stream_data.unread_count = stream_post_filter_unread_count;
            streams_dict.set(stream_key, new_stream_data);
            rerender_stream_inbox_header_if_needed(new_stream_data, old_stream_data);
            topics_dict.set(stream_key, get_sorted_row_dict(topics_dict.get(stream_key)));
            insert_topics(topic_keys_to_insert, stream_key);
        } else {
            topics_dict.delete(stream_key);
            streams_dict.delete(stream_key);
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
        case COLUMNS.ACTION_MENU: {
            focus_class = ".inbox-stream-menu";
        }
    }

    return focus_class;
}

function get_focus_class_for_row() {
    let focus_class = ".inbox-left-part";
    switch (col_focus) {
        case COLUMNS.UNREAD_COUNT: {
            focus_class = ".unread_count";
            break;
        }
        case COLUMNS.ACTION_MENU: {
            focus_class = ".inbox-topic-menu";
            break;
        }
        case COLUMNS.TOPIC_VISIBILITY: {
            focus_class = ".change_visibility_policy";
            break;
        }
    }
    return focus_class;
}

function is_element_visible(element_position) {
    const element_above = document.querySelector("#inbox-filters");
    const element_down = document.querySelector("#compose");
    const visible_top = element_above.getBoundingClientRect().bottom;
    const visible_bottom = element_down.getBoundingClientRect().top;

    if (element_position.top >= visible_top && element_position.bottom <= visible_bottom) {
        return true;
    }
    return false;
}

function center_focus_if_offscreen() {
    // Move focused to row to visible area so to avoid
    // it being under compose box or inbox filters.
    const $elt = $(".inbox-row:focus, .inbox-header:focus");
    if ($elt.length === 0) {
        return;
    }

    const elt_pos = $elt[0].getBoundingClientRect();
    if (is_element_visible(elt_pos)) {
        // Element is visible.
        return;
    }

    // Scroll element into center if offscreen.
    $elt[0].scrollIntoView({block: "center"});
}

function move_focus_to_visible_area() {
    // Focus on the row below inbox filters if the focused
    // row is not visible.
    if (!is_list_focused()) {
        return;
    }

    const $all_rows = get_all_rows();
    if ($all_rows.length <= 3) {
        // No need to process anything if there are only a few rows.
        return;
    }

    if (row_focus >= $all_rows.length) {
        row_focus = $all_rows.length - 1;
        revive_current_focus();
    }

    const elt_pos = $all_rows[row_focus].getBoundingClientRect();
    if (is_element_visible(elt_pos)) {
        return;
    }

    const INBOX_ROW_HEIGHT = 30;
    const position = $("#inbox-filters")[0].getBoundingClientRect();
    const inbox_center_x = (position.left + position.right) / 2;
    // We are aiming to get the first row if it is completely visible or the second row.
    const inbox_row_below_filters = position.bottom + INBOX_ROW_HEIGHT;
    const $element_in_row = $(document.elementFromPoint(inbox_center_x, inbox_row_below_filters));

    let $inbox_row = $element_in_row.closest(".inbox-row");
    if (!$inbox_row.length) {
        $inbox_row = $element_in_row.closest(".inbox-header");
    }

    row_focus = $all_rows.index($inbox_row);
    revive_current_focus();
}

export function is_in_focus() {
    // Check if user is focused on
    // inbox
    return (
        is_visible() &&
        !compose_state.composing() &&
        !popovers.any_active() &&
        !sidebar_ui.any_sidebar_expanded_as_overlay() &&
        !overlays.any_active() &&
        !modals.any_active() &&
        !$(".home-page-input").is(":focus")
    );
}

export function initialize() {
    $(document).on(
        "scroll",
        _.throttle(() => {
            move_focus_to_visible_area();
        }, 50),
    );

    $("body").on(
        "keyup",
        "#inbox-search",
        _.debounce(() => {
            search_and_update();
        }, 300),
    );

    $("body").on("keydown", ".inbox-header", (e) => {
        if (e.metaKey || e.ctrlKey) {
            return;
        }

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
        focus_clicked_list_element($elt);
        collapse_or_expand(container_id);
        e.stopPropagation();
    });

    $("body").on("keydown", ".inbox-row", (e) => {
        if (e.metaKey || e.ctrlKey) {
            return;
        }

        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
            e.stopPropagation();

            const $elt = $(e.currentTarget);
            $elt.find(get_focus_class_for_row()).trigger("click");
        }
    });

    $("body").on("click", "#inbox-list .inbox-left-part-wrapper", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        const $elt = $(e.currentTarget);
        col_focus = COLUMNS.RECIPIENT;
        focus_clicked_list_element($elt);
        window.location.href = $elt.find("a").attr("href");
    });

    $("body").on("click", "#inbox-list .on_hover_dm_read", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $elt = $(e.currentTarget);
        col_focus = COLUMNS.UNREAD_COUNT;
        focus_clicked_list_element($elt);
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
        focus_inbox_search();
        update_triggered_by_user = true;
    });

    $("body").on("click", "#inbox-list .on_hover_topic_read", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $elt = $(e.currentTarget);
        col_focus = COLUMNS.UNREAD_COUNT;
        focus_clicked_list_element($elt);
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

    $("body").on("click", "#inbox-clear-search", () => {
        $("#inbox-search").val("");
        search_and_update();
        focus_inbox_search();
    });

    $("body").on("click", "#inbox-search", () => {
        current_focus_id = INBOX_SEARCH_ID;
        compose_closed_ui.set_standard_text_for_reply_button();
    });

    // Mute topic in a unmuted stream
    $("body").on("click", "#inbox-list .stream_unmuted.on_hover_topic_mute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.MUTED,
        );
    });

    // Unmute topic in a unmuted stream
    $("body").on("click", "#inbox-list .stream_unmuted.on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    // Unmute topic in a muted stream
    $("body").on("click", "#inbox-list .stream_muted.on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.UNMUTED,
        );
    });

    // Mute topic in a muted stream
    $("body").on("click", "#inbox-list .stream_muted.on_hover_topic_mute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    $(document).on("compose_canceled.zulip", () => {
        if (is_visible()) {
            revive_current_focus();
        }
    });
}
