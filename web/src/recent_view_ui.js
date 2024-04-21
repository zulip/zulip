import $ from "jquery";
import _ from "lodash";

import * as typeahead from "../shared/src/typeahead";
import render_introduce_zulip_view_modal from "../templates/introduce_zulip_view_modal.hbs";
import render_recent_view_filters from "../templates/recent_view_filters.hbs";
import render_recent_view_row from "../templates/recent_view_row.hbs";
import render_recent_view_body from "../templates/recent_view_table.hbs";
import render_user_with_status_icon from "../templates/user_with_status_icon.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import * as compose_closed_ui from "./compose_closed_ui";
import * as compose_state from "./compose_state";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {localstorage} from "./localstorage";
import * as message_store from "./message_store";
import * as message_util from "./message_util";
import * as modals from "./modals";
import * as muted_users from "./muted_users";
import * as onboarding_steps from "./onboarding_steps";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as recent_senders from "./recent_senders";
import * as recent_view_data from "./recent_view_data";
import * as recent_view_util from "./recent_view_util";
import * as scroll_util from "./scroll_util";
import * as sidebar_ui from "./sidebar_ui";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_util from "./ui_util";
import * as unread from "./unread";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_topics from "./user_topics";
import * as views_util from "./views_util";

let topics_widget;
let filters_dropdown_widget;
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

// If user clicks a topic in Recent Conversations, then
// we store that topic here so that we can restore focus
// to that topic when user revisits.
let last_visited_topic = "";
let row_focus = 0;
// Start focus on the topic column, so Down+Enter works to visit a topic.
let col_focus = 1;

export const COLUMNS = {
    stream: 0,
    topic: 1,
    read: 2,
    mute: 3,
};

// The number of selectable actions in a Recent Conversations view.
// Used to implement wraparound of elements with the right/left keys.
// Must be increased when we add new actions, or rethought if we add
// optional actions that only appear in some rows.
const MAX_SELECTABLE_TOPIC_COLS = 4;
const MAX_SELECTABLE_DIRECT_MESSAGE_COLS = 3;

// we use localstorage to persist the recent topic filters
const ls_key = "recent_topic_filters";
const ls_dropdown_key = "recent_topic_dropdown_filters";
const ls = localstorage();

let filters = new Set();
let dropdown_filters = new Set();

const recent_conversation_key_prefix = "recent_conversation:";

export function clear_for_tests() {
    filters.clear();
    dropdown_filters.clear();
    recent_view_data.conversations.clear();
    topics_widget = undefined;
}

export function save_filters() {
    ls.set(ls_key, [...filters]);
    ls.set(ls_dropdown_key, [...dropdown_filters]);
}

export function is_in_focus() {
    // Check if user is focused on Recent Conversations.
    return (
        recent_view_util.is_visible() &&
        !compose_state.composing() &&
        !popovers.any_active() &&
        !sidebar_ui.any_sidebar_expanded_as_overlay() &&
        !overlays.any_active() &&
        !modals.any_active() &&
        !$(".home-page-input").is(":focus")
    );
}

export function set_default_focus() {
    // If at any point we are confused about the currently
    // focused element, we switch focus to search.
    $current_focus_elem = $("#recent_view_search");
    $current_focus_elem.trigger("focus");
    compose_closed_ui.set_standard_text_for_reply_button();
}

// When there are no messages loaded, we don't show a banner yet.
const NO_MESSAGES_LOADED = 0;
// When some messages are loaded, but we're still loading newer messages,
// we show a simple loading banner.
const SOME_MESSAGES_LOADED = 1;
// Once we've found the newest message, we allow the user to load
// more messages further back in time.
const SOME_MESSAGES_LOADED_INCLUDING_NEWEST = 2;
// Once all messages are loaded, we hide the banner.
const ALL_MESSAGES_LOADED = 3;

let loading_state = NO_MESSAGES_LOADED;
let oldest_message_timestamp = Number.POSITIVE_INFINITY;

export function set_oldest_message_date(msg_list_data) {
    const has_found_oldest = msg_list_data.fetch_status.has_found_oldest();
    const has_found_newest = msg_list_data.fetch_status.has_found_newest();

    const first_message_timestamp = msg_list_data.first()?.timestamp ?? Number.POSITIVE_INFINITY;
    oldest_message_timestamp = Math.min(first_message_timestamp, oldest_message_timestamp);

    if (has_found_oldest) {
        loading_state = ALL_MESSAGES_LOADED;
    } else if (has_found_newest) {
        loading_state = SOME_MESSAGES_LOADED_INCLUDING_NEWEST;
    } else {
        loading_state = SOME_MESSAGES_LOADED;
    }

    // We might be loading messages in another narrow before the recent view
    // is shown, so we keep the state updated and update the banner only
    // once it's actually rendered.
    if ($("#recent_view_table table tbody").length) {
        update_load_more_banner();
    }
}

function update_load_more_banner() {
    if (loading_state === NO_MESSAGES_LOADED) {
        return;
    }

    if (loading_state === ALL_MESSAGES_LOADED) {
        $(".recent-view-load-more-container").toggleClass("notvisible", true);
        return;
    }

    if (!topics_widget?.all_rendered()) {
        $(".recent-view-load-more-container").toggleClass("notvisible", true);
        return;
    }

    // There are some messages loaded, but not all messages yet. The banner was
    // hidden on page load, and we make sure to show it now that there are messages
    // we can display.
    $(".recent-view-load-more-container").toggleClass("notvisible", false);

    // Until we've found the newest message, we only show the banner with a messages
    // explaining we're still fetching messages. We don't allow the user to fetch
    // more messages.
    if (loading_state === SOME_MESSAGES_LOADED) {
        return;
    }

    const $button = $(".recent-view-load-more-container .fetch-messages-button");
    const $button_label = $(".recent-view-load-more-container .button-label");
    const $banner_text = $(".recent-view-load-more-container .last-fetched-message");

    $button.toggleClass("notvisible", false);

    const time_obj = new Date(oldest_message_timestamp * 1000);
    const time_string = timerender.get_localized_date_or_time_for_format(
        time_obj,
        "full_weekday_dayofyear_year_time",
    );
    $banner_text.text($t({defaultMessage: "Showing messages since {time_string}."}, {time_string}));

    $button_label.toggleClass("invisible", false);
    $button.prop("disabled", false);
    loading.destroy_indicator(
        $(".recent-view-load-more-container .fetch-messages-button .loading-indicator"),
    );
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
    // We use CSS method for finding row type until topics_widget gets initialized.
    if (!topics_widget) {
        const $topic_rows = $("#recent_view_table table tbody tr");
        const $topic_row = $topic_rows.eq(row);
        const is_private = $topic_row.attr("data-private");
        if (is_private) {
            return "private";
        }
        return "stream";
    }

    const current_list = topics_widget.get_current_list();
    const current_row = current_list[row];
    return current_row.type;
}

function get_max_selectable_cols(row) {
    // returns maximum number of columns in stream message or direct message row.
    const type = get_row_type(row);
    if (type === "private") {
        return MAX_SELECTABLE_DIRECT_MESSAGE_COLS;
    }
    return MAX_SELECTABLE_TOPIC_COLS;
}

function set_table_focus(row, col, using_keyboard) {
    if (topics_widget.get_current_list().length === 0) {
        // If there are no topics to show, we don't want to focus on the table.
        set_default_focus();
        return true;
    }

    const $topic_rows = $("#recent_view_table table tbody tr");
    if ($topic_rows.length === 0 || row < 0 || row >= $topic_rows.length) {
        row_focus = 0;
        // return focus back to filters if we cannot focus on the table.
        set_default_focus();
        return true;
    }

    const unread = has_unread(row);
    if (col === 2 && !unread) {
        col = 1;
        col_focus = 1;
    }
    const type = get_row_type(row);
    if (col === 3 && type === "private") {
        col = unread ? 2 : 1;
        col_focus = col;
    }

    const $topic_row = $topic_rows.eq(row);
    // We need to allow table to render first before setting focus.
    setTimeout(
        () => $topic_row.find(".recent_view_focusable").eq(col).children().trigger("focus"),
        0,
    );
    $current_focus_elem = "table";

    if (using_keyboard) {
        const scroll_element = document.querySelector(
            "#recent_view_table .table_fix_head .simplebar-content-wrapper",
        );
        const half_height_of_visible_area = scroll_element.offsetHeight / 2;
        const topic_offset = topic_offset_to_visible_area($topic_row);

        if (topic_offset === "above") {
            scroll_element.scrollBy({top: -1 * half_height_of_visible_area});
        } else if (topic_offset === "below") {
            scroll_element.scrollBy({top: half_height_of_visible_area});
        }
    }

    // TODO: This fake "message" object is designed to allow using the
    // get_recipient_label helper inside compose_closed_ui. Surely
    // there's a more readable way to write this code.
    // Similar code is present in Inbox.
    let message;
    if (type === "private") {
        message = {
            display_reply_to: $topic_row.find(".recent_topic_name a").text(),
        };
    } else {
        const stream_name = $topic_row.find(".recent_topic_stream a").text();
        const stream = stream_data.get_sub_by_name(stream_name);
        message = {
            stream_id: stream?.stream_id,
            topic: $topic_row.find(".recent_topic_name a").text(),
        };
    }
    compose_closed_ui.update_reply_recipient_label(message);
    return true;
}

export function get_focused_row_message() {
    if (is_table_focused()) {
        if (topics_widget.get_current_list().length === 0) {
            return undefined;
        }

        const $topic_rows = $("#recent_view_table table tbody tr");
        const $topic_row = $topic_rows.eq(row_focus);
        const conversation_id = $topic_row.attr("id").slice(recent_conversation_key_prefix.length);
        const topic_last_msg_id = recent_view_data.conversations.get(conversation_id).last_msg_id;
        return message_store.get(topic_last_msg_id);
    }
    return undefined;
}

export function revive_current_focus() {
    // After re-render, the current_focus_elem is no longer linked
    // to the focused element, this function attempts to revive the
    // link and focus to the element prior to the rerender.

    // We try to avoid setting focus when user
    // is not focused on Recent Conversations.
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
            // then the topic will not be in Recent Conversations data.
            if (recent_view_data.conversations.get(last_visited_topic) !== undefined) {
                const topic_last_msg_id =
                    recent_view_data.conversations.get(last_visited_topic).last_msg_id;
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

    if ($current_focus_elem.hasClass("dropdown-widget-button")) {
        $("#recent-view-filter_widget").trigger("focus");
        return true;
    }

    const filter_button = $current_focus_elem.data("filter");
    if (!filter_button) {
        set_default_focus();
    } else {
        $current_focus_elem = $("#recent_view_filter_buttons").find(
            `[data-filter='${CSS.escape(filter_button)}']`,
        );
        $current_focus_elem.trigger("focus");
    }
    return true;
}

export function show_loading_indicator() {
    loading.make_indicator($("#recent_view_loading_messages_indicator"));
    $("#recent_view_table tbody").removeClass("required-text");
}

export function hide_loading_indicator() {
    $("#recent_view_bottom_whitespace").hide();
    loading.destroy_indicator($("#recent_view_loading_messages_indicator"), {
        abs_positioned: false,
    });
}

export function process_messages(messages, msg_list_data) {
    // Always synced with messages in all_messages_data.

    let conversation_data_updated = false;
    if (messages.length > 0) {
        for (const msg of messages) {
            if (recent_view_data.process_message(msg)) {
                conversation_data_updated = true;
            }
        }
    }

    if (msg_list_data) {
        // Update the recent view UI's understanding of which messages
        // we have available for the recent view.
        set_oldest_message_date(msg_list_data);
    }

    // Only rerender if conversation data actually changed.
    if (conversation_data_updated) {
        complete_rerender();
    }
}

function message_to_conversation_unread_count(msg) {
    if (msg.type === "private") {
        return unread.num_unread_for_user_ids_string(msg.to_user_ids);
    }
    return unread.num_unread_for_topic(msg.stream_id, msg.topic);
}

export function get_pm_tooltip_data(user_ids_string) {
    const user_id = Number.parseInt(user_ids_string, 10);
    const person = people.get_by_user_id(user_id);

    if (person.is_bot) {
        const bot_owner = people.get_bot_owner_user(person);

        if (bot_owner) {
            const bot_owner_name = $t(
                {defaultMessage: "Owner: {name}"},
                {name: bot_owner.full_name},
            );

            return {
                first_line: person.full_name,
                second_line: bot_owner_name,
            };
        }

        // Bot does not have an owner.
        return {
            first_line: person.full_name,
            second_line: "",
            third_line: "",
        };
    }

    const last_seen = buddy_data.user_last_seen_time_status(user_id);

    // Users does not have a status.
    return {
        first_line: last_seen,
        second_line: "",
        third_line: "",
    };
}

function format_conversation(conversation_data) {
    const context = {};
    const last_msg = message_store.get(conversation_data.last_msg_id);
    const time = new Date(last_msg.timestamp * 1000);
    const type = last_msg.type;
    context.full_last_msg_date_time = timerender.get_full_datetime_clarification(time);
    context.conversation_key = recent_view_util.get_key_from_message(last_msg);
    context.unread_count = message_to_conversation_unread_count(last_msg);
    context.last_msg_time = timerender.relative_time_string_from_date(time);
    context.is_private = last_msg.type === "private";
    let all_senders;
    let senders;
    let displayed_other_senders;
    let extra_sender_ids;

    if (type === "stream") {
        const stream_info = sub_store.get(last_msg.stream_id);

        // Stream info
        context.stream_id = last_msg.stream_id;
        context.stream_name = stream_data.get_stream_name_from_id(last_msg.stream_id);
        context.stream_color = stream_info.color;
        context.stream_url = hash_util.by_stream_url(context.stream_id);
        context.invite_only = stream_info.invite_only;
        context.is_web_public = stream_info.is_web_public;
        // Topic info
        context.topic = last_msg.topic;
        context.topic_url = hash_util.by_stream_topic_url(context.stream_id, context.topic);

        // We hide the row according to filters or if it's muted.
        // We only supply the data to the topic rows and let jquery
        // display / hide them according to filters instead of
        // doing complete re-render.
        context.mention_in_unread = unread.topic_has_any_unread_mentions(
            context.stream_id,
            context.topic,
        );

        context.visibility_policy = user_topics.get_topic_visibility_policy(
            context.stream_id,
            context.topic,
        );
        // The following field is not specific to this context, but this is the
        // easiest way we've figured out for passing the data to the template rendering.
        context.all_visibility_policies = user_topics.all_visibility_policies;

        // Since the css for displaying senders in reverse order is much simpler,
        // we provide our handlebars with senders in opposite order.
        // Display in most recent sender first order.
        all_senders = recent_senders
            .get_topic_recent_senders(context.stream_id, context.topic)
            .reverse();
        senders = all_senders.slice(-MAX_AVATAR);

        // Collect extra sender fullname for tooltip
        extra_sender_ids = all_senders.slice(0, -MAX_AVATAR);
        displayed_other_senders = extra_sender_ids.slice(-MAX_EXTRA_SENDERS);
    } else if (type === "private") {
        // Direct message info
        context.user_ids_string = last_msg.to_user_ids;
        context.rendered_pm_with = last_msg.display_recipient
            .filter(
                (recipient) =>
                    !people.is_my_user_id(recipient.id) || last_msg.display_recipient.length === 1,
            )
            .map((user) =>
                render_user_with_status_icon({
                    name: people.get_display_full_name(user.id),
                    status_emoji_info: user_status.get_status_emoji(user.id),
                }),
            )
            .sort()
            .join(", ");
        context.recipient_id = last_msg.recipient_id;
        context.pm_url = last_msg.pm_with_url;
        context.is_group = last_msg.display_recipient.length > 2;

        if (!context.is_group) {
            const user_id = Number.parseInt(last_msg.to_user_ids, 10);
            const user = people.get_by_user_id(user_id);
            if (user.is_bot) {
                // We display the bot icon rather than a user circle for bots.
                context.is_bot = true;
            } else {
                context.user_circle_class = buddy_data.get_user_circle_class(user_id);
            }
        }

        // Since the css for displaying senders in reverse order is much simpler,
        // we provide our handlebars with senders in opposite order.
        // Display in most recent sender first order.
        // To match the behavior for streams, we display the set of users who've actually
        // participated, with the most recent participants first. It could make sense to
        // display the other recipients on the direct message conversation with different
        // styling, but it's important to not destroy the information of "who's actually
        // talked".
        all_senders = recent_senders
            .get_pm_recent_senders(context.user_ids_string)
            .participants.reverse();
        senders = all_senders.slice(-MAX_AVATAR);
        // Collect extra senders fullname for tooltip.
        extra_sender_ids = all_senders.slice(0, -MAX_AVATAR);
        displayed_other_senders = extra_sender_ids.slice(-MAX_EXTRA_SENDERS);
    }

    context.senders = people.sender_info_for_recent_view_row(senders);
    context.other_senders_count = Math.max(0, all_senders.length - MAX_AVATAR);
    extra_sender_ids = all_senders.slice(0, -MAX_AVATAR);
    const displayed_other_names = people.get_display_full_names(displayed_other_senders.reverse());

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
    context.other_sender_names_html = displayed_other_names
        .map((name) => _.escape(name))
        .join("<br />");
    context.last_msg_url = hash_util.by_conversation_and_time_url(last_msg);
    context.is_spectator = page_params.is_spectator;

    return context;
}

function get_topic_row(topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);
    const topic_key = recent_view_util.get_key_from_message(msg);
    return $(`#${CSS.escape(recent_conversation_key_prefix + topic_key)}`);
}

export function process_topic_edit(old_stream_id, old_topic, new_topic, new_stream_id) {
    // See `recent_senders.process_topic_edit` for
    // logic behind this and important notes on use of this function.
    recent_view_data.conversations.delete(recent_view_util.get_topic_key(old_stream_id, old_topic));

    const old_topic_msgs = message_util.get_messages_in_topic(old_stream_id, old_topic);
    process_messages(old_topic_msgs);

    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_messages_in_topic(new_stream_id, new_topic);
    process_messages(new_topic_msgs);
}

export function topic_in_search_results(keyword, stream_name, topic) {
    if (keyword === "") {
        return true;
    }
    const text = (stream_name + " " + topic).toLowerCase();
    return typeahead.query_matches_string_in_any_order(keyword, text, " ");
}

export function update_topics_of_deleted_message_ids(message_ids) {
    const topics_to_rerender = message_util.get_topics_for_message_ids(message_ids);

    for (const [stream_id, topic] of topics_to_rerender.values()) {
        recent_view_data.conversations.delete(recent_view_util.get_topic_key(stream_id, topic));
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
        const unread_count = message_to_conversation_unread_count(msg);
        if (unread_count === 0) {
            return true;
        }
    }

    if (!topic_data.participated && filters.has("participated")) {
        return true;
    }

    if (dropdown_filters.has(views_util.FILTERS.UNMUTED_TOPICS) && topic_data.type === "stream") {
        // We want to show the unmuted or followed topics within muted
        // streams in Recent Conversations.
        const topic_unmuted_or_followed = Boolean(
            user_topics.is_topic_unmuted_or_followed(msg.stream_id, msg.topic),
        );
        const topic_muted = Boolean(user_topics.is_topic_muted(msg.stream_id, msg.topic));
        const stream_muted = stream_data.is_muted(msg.stream_id);
        if (topic_muted || (stream_muted && !topic_unmuted_or_followed)) {
            return true;
        }
    }

    if (!filters.has("include_private") && topic_data.type === "private") {
        return true;
    }

    if (filters.has("include_private") && topic_data.type === "private") {
        const recipients = people.split_to_ints(msg.to_user_ids);

        if (recipients.every((id) => muted_users.is_user_muted(id))) {
            return true;
        }
    }

    if (
        dropdown_filters.has(views_util.FILTERS.FOLLOWED_TOPICS) &&
        topic_data.type === "stream" &&
        !user_topics.is_topic_followed(msg.stream_id, msg.topic)
    ) {
        return true;
    }

    if (
        dropdown_filters.has(views_util.FILTERS.UNMUTED_TOPICS) &&
        topic_data.type === "stream" &&
        (user_topics.is_topic_muted(msg.stream_id, msg.topic) ||
            stream_data.is_muted(msg.stream_id)) &&
        !user_topics.is_topic_unmuted_or_followed(msg.stream_id, msg.topic)
    ) {
        return true;
    }

    const search_keyword = $("#recent_view_search").val();
    const stream_name = stream_data.get_stream_name_from_id(msg.stream_id);
    if (!topic_in_search_results(search_keyword, stream_name, msg.topic)) {
        return true;
    }

    return false;
}

export function inplace_rerender(topic_key) {
    if (!recent_view_util.is_visible()) {
        return false;
    }
    if (!recent_view_data.conversations.has(topic_key)) {
        return false;
    }

    const topic_data = recent_view_data.conversations.get(topic_key);
    const $topic_row = get_topic_row(topic_data);
    // We cannot rely on `topic_widget.meta.filtered_list` to know
    // if a topic is rendered since the `filtered_list` might have
    // already been updated via other calls.
    const is_topic_rendered = $topic_row.length;
    // Resorting the topics_widget is important for the case where we
    // are rerendering because of message editing or new messages
    // arriving, since those operations often change the sort key.
    topics_widget.filter_and_sort();
    const current_topics_list = topics_widget.get_current_list();
    if (is_topic_rendered && filters_should_hide_topic(topic_data)) {
        // Since the row needs to be removed from DOM, we need to adjust `row_focus`
        // if the row being removed is focused and is the last row in the list.
        // This prevents the row_focus either being reset to the first row or
        // middle of the visible table rows.
        // We need to get the current focused row details from DOM since we cannot
        // rely on `current_topics_list` since it has already been updated and row
        // doesn't exist inside it.
        const row_is_focused = get_focused_row_message()?.id === topic_data.last_msg_id;
        if (row_is_focused && row_focus >= current_topics_list.length) {
            row_focus = current_topics_list.length - 1;
        }
        topics_widget.remove_rendered_row($topic_row);
    } else if (!is_topic_rendered && filters_should_hide_topic(topic_data)) {
        // In case `topic_row` is not present, our job is already done here
        // since it has not been rendered yet and we already removed it from
        // the filtered list in `topic_widget`. So, it won't be displayed in
        // the future too.
    } else if (is_topic_rendered && !filters_should_hide_topic(topic_data)) {
        // Only a re-render is required in this case.
        topics_widget.render_item(topic_data);
    } else {
        // Final case: !is_topic_rendered && !filters_should_hide_topic(topic_data).
        topics_widget.insert_rendered_row(topic_data, () =>
            current_topics_list.findIndex(
                (list_item) => list_item.last_msg_id === topic_data.last_msg_id,
            ),
        );
    }
    setTimeout(revive_current_focus, 0);
    return true;
}

export function update_topic_visibility_policy(stream_id, topic) {
    const key = recent_view_util.get_topic_key(stream_id, topic);
    if (!recent_view_data.conversations.has(key)) {
        // we receive mute request for a topic we are
        // not tracking currently
        return false;
    }

    inplace_rerender(key);
    return true;
}

export function update_topic_unread_count(message) {
    const topic_key = recent_view_util.get_key_from_message(message);
    inplace_rerender(topic_key);
}

export function set_filter(filter) {
    // This function updates the `filters` variable
    // after user clicks on one of the filter buttons
    // based on `btn-recent-selected` class and current
    // set `filters`.

    // Get the button which was clicked.
    const $filter_elem = $("#recent_view_filter_buttons").find(
        `[data-filter="${CSS.escape(filter)}"]`,
    );

    if ($filter_elem.hasClass("btn-recent-selected")) {
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
    for (const filter of filters) {
        $("#recent_view_filter_buttons")
            .find(`[data-filter="${CSS.escape(filter)}"]`)
            .addClass("btn-recent-selected")
            .attr("aria-checked", "true");
    }
}

function get_recent_view_filters_params() {
    return {
        filter_unread: filters.has("unread"),
        filter_participated: filters.has("participated"),
        filter_muted: filters.has("include_muted"),
        filter_pm: filters.has("include_private"),
        is_spectator: page_params.is_spectator,
    };
}

function setup_dropdown_filters_widget() {
    filters_dropdown_widget = new dropdown_widget.DropdownWidget({
        ...views_util.COMMON_DROPDOWN_WIDGET_PARAMS,
        widget_name: "recent-view-filter",
        item_click_callback: filter_click_handler,
        $events_container: $("#recent_view_filter_buttons"),
        default_id: dropdown_filters.values().next().value,
    });
    filters_dropdown_widget.setup();
}

export function update_filters_view() {
    const rendered_filters = render_recent_view_filters(get_recent_view_filters_params());
    $("#recent_filters_group").html(rendered_filters);
    show_selected_filters();
    filters_dropdown_widget.render();
    topics_widget.hard_redraw();
}

function sort_comparator(a, b) {
    // compares strings in lowercase and returns -1, 0, 1
    if (a.toLowerCase() > b.toLowerCase()) {
        return 1;
    } else if (a.toLowerCase() === b.toLowerCase()) {
        return 0;
    }
    return -1;
}

function stream_sort(a, b) {
    if (a.type === b.type) {
        const a_msg = message_store.get(a.last_msg_id);
        const b_msg = message_store.get(b.last_msg_id);

        if (a.type === "stream") {
            const a_stream_name = stream_data.get_stream_name_from_id(a_msg.stream_id);
            const b_stream_name = stream_data.get_stream_name_from_id(b_msg.stream_id);
            return sort_comparator(a_stream_name, b_stream_name);
        }
        return sort_comparator(a_msg.display_reply_to, b_msg.display_reply_to);
    }
    // if type is not same sort between "private" and "stream"
    return sort_comparator(a.type, b.type);
}

function topic_sort_key(conversation_data) {
    const message = message_store.get(conversation_data.last_msg_id);
    if (message.type === "private") {
        return message.display_reply_to;
    }
    return message.topic;
}

function topic_sort(a, b) {
    return sort_comparator(topic_sort_key(a), topic_sort_key(b));
}

function unread_count(conversation_data) {
    const message = message_store.get(conversation_data.last_msg_id);
    return message_to_conversation_unread_count(message);
}

function unread_sort(a, b) {
    const a_unread_count = unread_count(a);
    const b_unread_count = unread_count(b);
    if (a_unread_count !== b_unread_count) {
        return a_unread_count - b_unread_count;
    }
    return a.last_msg_id - b.last_msg_id;
}

function topic_offset_to_visible_area(topic_row) {
    const $topic_row = $(topic_row);
    if ($topic_row.length === 0) {
        // TODO: There is a possibility of topic_row being undefined here
        // which logically doesn't makes sense. Find out the case and
        // document it here.
        // We return undefined here since we don't know anything about the
        // topic and the callers will take care of undefined being returned.
        return undefined;
    }
    const $scroll_container = $("#recent_view_table .table_fix_head");
    const thead_height = $scroll_container.find("thead").outerHeight(true);
    const scroll_container_props = $scroll_container[0].getBoundingClientRect();

    // Since user cannot see row under thead, exclude it as part of the scroll container.
    const scroll_container_top = scroll_container_props.top + thead_height;
    const compose_height = $("#compose").outerHeight(true);
    const scroll_container_bottom = scroll_container_props.bottom - compose_height;

    const topic_props = $topic_row[0].getBoundingClientRect();

    // Topic is above the visible scroll region.
    if (topic_props.top < scroll_container_top) {
        return "above";
        // Topic is below the visible scroll region.
    } else if (topic_props.bottom > scroll_container_bottom) {
        return "below";
    }

    // Topic is visible
    return "visible";
}

function recenter_focus_if_off_screen() {
    const table_wrapper_element = document.querySelector("#recent_view_table .table_fix_head");
    const $topic_rows = $("#recent_view_table table tbody tr");

    if (row_focus >= $topic_rows.length) {
        // User used a filter which reduced
        // the number of visible rows.
        return;
    }
    let $topic_row = $topic_rows.eq(row_focus);
    const topic_offset = topic_offset_to_visible_area($topic_row);
    if (topic_offset === undefined) {
        // We don't need to return here since technically topic_offset is not visible.
        blueslip.error("Unable to get topic from row", {row_focus});
    }

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

function callback_after_render() {
    update_load_more_banner();
    setTimeout(revive_current_focus, 0);
}

function filter_click_handler(event, dropdown, widget) {
    event.preventDefault();
    event.stopPropagation();

    if (page_params.is_spectator) {
        // Filter buttons are disabled for spectator.
        return;
    }

    const filter_id = $(event.currentTarget).attr("data-unique-id");
    // We don't support multiple filters yet, so we clear existing and add the new filter.
    dropdown_filters = new Set([filter_id]);
    dropdown.hide();
    widget.render();
    save_filters();

    topics_widget.hard_redraw();
}

export function complete_rerender() {
    if (!recent_view_util.is_visible()) {
        return;
    }

    // Show topics list
    const mapped_topic_values = [...recent_view_data.get_conversations().values()];

    if (topics_widget) {
        topics_widget.replace_list_data(mapped_topic_values);
        return;
    }

    const rendered_body = render_recent_view_body({
        search_val: $("#recent_view_search").val() || "",
        ...get_recent_view_filters_params(),
    });
    $("#recent_view_table").html(rendered_body);

    // `show_selected_filters` needs to be called after the Recent
    // Conversations view has been added to the DOM, to ensure that filters
    // have the correct classes (checked or not) if Recent Conversations
    // was not the first view loaded in the app.
    show_selected_filters();

    const $container = $("#recent_view_table table tbody");
    $container.empty();
    topics_widget = ListWidget.create($container, mapped_topic_values, {
        name: "recent_view_table",
        get_item: ListWidget.default_get_item,
        $parent_container: $("#recent_view_table"),
        modifier_html(item) {
            return render_recent_view_row(format_conversation(item));
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
            unread_sort,
            ...ListWidget.generic_sort_functions("numeric", ["last_msg_id"]),
        },
        html_selector: get_topic_row,
        $simplebar_container: $("#recent_view_table .table_fix_head"),
        callback_after_render,
        is_scroll_position_for_render,
        post_scroll__pre_render_callback() {
            // Update the focused element for keyboard navigation if needed.
            recenter_focus_if_off_screen();
        },
        get_min_load_count,
    });
    setup_dropdown_filters_widget();
}

export function show() {
    views_util.show({
        highlight_view_in_left_sidebar: left_sidebar_navigation_area.highlight_recent_view,
        $view: $("#recent_view"),
        // We want to show `new stream message` instead of
        // `new topic`, which we are already doing in this
        // function. So, we reuse it here.
        update_compose: compose_closed_ui.update_buttons_for_non_specific_views,
        is_recent_view: true,
        is_visible: recent_view_util.is_visible,
        set_visible: recent_view_util.set_visible,
        complete_rerender,
    });

    if (onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("intro_recent_view_modal")) {
        const html_body = render_introduce_zulip_view_modal({
            zulip_view: "recent_conversations",
            current_home_view_and_escape_navigation_enabled:
                user_settings.web_home_view === "recent_topics" &&
                user_settings.web_escape_navigates_to_home_view,
        });
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Welcome to <b>recent conversations</b>!"}),
            html_body,
            html_submit_button: $t_html({defaultMessage: "Continue"}),
            on_click() {},
            single_footer_button: true,
            focus_submit_on_open: true,
        });
        onboarding_steps.post_onboarding_step_as_read("intro_recent_view_modal");
    }
}

function filter_buttons() {
    return $("#recent_filters_group").children();
}

export function hide() {
    views_util.hide({
        $view: $("#recent_view"),
        set_visible: recent_view_util.set_visible,
    });
}

function is_focus_at_last_table_row() {
    return row_focus >= topics_widget.get_current_list().length - 1;
}

function has_unread(row) {
    const last_msg_id = topics_widget.get_current_list()[row].last_msg_id;
    const last_msg = message_store.get(last_msg_id);
    if (last_msg.type === "stream") {
        return unread.num_unread_for_topic(last_msg.stream_id, last_msg.topic) > 0;
    }
    return unread.num_unread_for_user_ids_string(last_msg.to_user_ids) > 0;
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

function down_arrow_navigation() {
    row_focus += 1;
}

function get_page_up_down_delta() {
    const table_height = $("#recent_view_table .table_fix_head").height();
    const table_header_height = $("#recent_view_table table thead").height();
    const compose_box_height = $("#compose").height();
    // One usually wants PageDown to move what had been the bottom row
    // to now be at the top, so one can be confident one will see
    // every row using it. This offset helps achieve that goal.
    //
    // See navigate.amount_to_paginate for similar logic in the message feed.
    const scrolling_reduction_to_maintain_context = 75;

    const delta =
        table_height -
        table_header_height -
        compose_box_height -
        scrolling_reduction_to_maintain_context;
    return delta;
}

function page_up_navigation() {
    const $scroll_container = scroll_util.get_scroll_element(
        $("#recent_view_table .table_fix_head"),
    );
    const delta = get_page_up_down_delta();
    const new_scrollTop = $scroll_container.scrollTop() - delta;
    if (new_scrollTop <= 0) {
        row_focus = 0;
    }
    $scroll_container.scrollTop(new_scrollTop);
}

function page_down_navigation() {
    const $scroll_container = scroll_util.get_scroll_element(
        $("#recent_view_table .table_fix_head"),
    );
    const delta = get_page_up_down_delta();
    const new_scrollTop = $scroll_container.scrollTop() + delta;
    const table_height = $("#recent_view_table .table_fix_head").height();
    if (new_scrollTop >= table_height) {
        row_focus = topics_widget.get_current_list().length - 1;
    }
    $scroll_container.scrollTop(new_scrollTop);
}

function check_row_type_transition(row, col) {
    // This function checks if the row is transitioning
    // from type "Direct messages" to "Stream" or vice versa.
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

    if ($elt.attr("id") === "recent_view_search") {
        // Since the search box a text area, we want the browser to handle
        // Left/Right and selection within the widget; but if the user
        // arrows off the edges, we should move focus to the adjacent widgets..
        const textInput = $("#recent_view_search").get(0);
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
            case "open_recent_view":
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
                $current_focus_elem = $("#recent_view_search");
                compose_closed_ui.set_standard_text_for_reply_button();
                return true;
            case "escape":
                if (is_table_focused()) {
                    return false;
                }
                set_table_focus(row_focus, col_focus);
                return true;
        }
    } else if ($elt.hasClass("btn-recent-filters") || $elt.hasClass("dropdown-widget-button")) {
        switch (input_key) {
            case "click":
                $current_focus_elem = $elt;
                return true;
            case "shift_tab":
            case "vim_left":
            case "left_arrow":
                if (filter_buttons().first()[0] === $elt[0]) {
                    $current_focus_elem = $("#recent_view_search");
                } else {
                    $current_focus_elem = $elt.prev();
                }
                break;
            case "tab":
            case "vim_right":
            case "right_arrow":
                if (filter_buttons().last()[0] === $elt[0]) {
                    $current_focus_elem = $("#recent_view_search");
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
        // Don't process hotkeys in table if there are no rows.
        if (!topics_widget || topics_widget.get_current_list().length === 0) {
            return true;
        }

        // For arrowing around the table of topics, we implement left/right
        // wraparound.  Going off the top or the bottom takes one
        // to the navigation at the top (see set_table_focus).
        switch (input_key) {
            case "escape":
                return false;
            case "open_recent_view":
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
            case "down_arrow":
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
                down_arrow_navigation();
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
            case "page_up":
                page_up_navigation();
                return true;
            case "page_down":
                page_down_navigation();
                return true;
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

function load_filters() {
    // load filters from local storage.
    if (!page_params.is_spectator) {
        // A user may have a stored filter and can log out
        // to see web public view. This ensures no filters are
        // selected for spectators.
        filters = new Set(ls.get(ls_key));
        dropdown_filters = new Set(ls.get(ls_dropdown_key));
    }
    // Verify that the dropdown_filters are valid.
    const valid_filters = new Set(Object.values(views_util.FILTERS));
    // If saved filters are not in the list of valid filters, we reset to default.
    const is_subset = [...dropdown_filters].every((filter) => valid_filters.has(filter));
    if (dropdown_filters.size === 0 || !is_subset) {
        dropdown_filters = new Set([views_util.FILTERS.UNMUTED_TOPICS]);
    }
}

export function initialize({
    on_click_participant,
    on_mark_pm_as_read,
    on_mark_topic_as_read,
    maybe_load_older_messages,
}) {
    load_filters();

    $("body").on("click", "#recent_view_table .recent_view_participant_avatar", function (e) {
        const participant_user_id = Number.parseInt($(this).parent().attr("data-user-id"), 10);
        e.stopPropagation();
        on_click_participant(this, participant_user_id);
    });

    $("body").on(
        "keydown",
        ".on_hover_topic_mute, .on_hover_topic_unmute",
        ui_util.convert_enter_to_click,
    );

    // Mute topic in a unmuted stream
    $("body").on("click", "#recent_view_table .stream_unmuted.on_hover_topic_mute", (e) => {
        e.stopPropagation();
        const $elt = $(e.target);
        const topic_row_index = $elt.closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.mute);
        user_topics.set_visibility_policy_for_element(
            $elt,
            user_topics.all_visibility_policies.MUTED,
        );
    });

    // Unmute topic in a unmuted stream
    $("body").on("click", "#recent_view_table .stream_unmuted.on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        const $elt = $(e.target);
        const topic_row_index = $elt.closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.mute);
        user_topics.set_visibility_policy_for_element(
            $elt,
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    // Unmute topic in a muted stream
    $("body").on("click", "#recent_view_table .stream_muted.on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        const $elt = $(e.target);
        const topic_row_index = $elt.closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.mute);
        user_topics.set_visibility_policy_for_element(
            $elt,
            user_topics.all_visibility_policies.UNMUTED,
        );
    });

    // Mute topic in a muted stream
    $("body").on("click", "#recent_view_table .stream_muted.on_hover_topic_mute", (e) => {
        e.stopPropagation();
        const $elt = $(e.target);
        const topic_row_index = $elt.closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.mute);
        user_topics.set_visibility_policy_for_element(
            $elt,
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    $("body").on("click", "#recent_view_search", (e) => {
        e.stopPropagation();
        change_focused_element($(e.target), "click");
    });

    $("body").on("click", "#recent_view_table .on_hover_topic_read", (e) => {
        e.stopPropagation();
        const $elt = $(e.currentTarget);
        const topic_row_index = $elt.closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.read);
        const user_ids_string = $elt.attr("data-user-ids-string");
        if (user_ids_string) {
            // direct message row
            on_mark_pm_as_read(user_ids_string);
        } else {
            // Stream row
            const stream_id = Number.parseInt($elt.attr("data-stream-id"), 10);
            const topic = $elt.attr("data-topic-name");
            on_mark_topic_as_read(stream_id, topic);
        }
        // If `unread` filter is selected, the focused topic row gets removed
        // and we automatically move one row down.
        if (!filters.has("unread")) {
            change_focused_element($elt, "down_arrow");
        }
    });

    $("body").on("keydown", ".on_hover_topic_read", ui_util.convert_enter_to_click);

    $("body").on("click", ".btn-recent-filters", (e) => {
        e.stopPropagation();
        if (page_params.is_spectator) {
            // Filter buttons are disabled for spectator.
            return;
        }

        change_focused_element($(e.target), "click");
        set_filter(e.currentTarget.dataset.filter);
        update_filters_view();
        revive_current_focus();
    });

    $("body").on("click", "#recent-view-filter_widget", (e) => {
        if (page_params.is_spectator) {
            // Filter buttons are disabled for spectator.
            return;
        }

        change_focused_element($(e.currentTarget), "click");
    });

    $("body").on("click", "td.recent_topic_stream", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        e.stopPropagation();
        const topic_row_index = $(e.target).closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.stream);
        window.location.href = $(e.currentTarget).find("a").attr("href");
    });

    $("body").on("click", "td.recent_topic_name", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        e.stopPropagation();
        // The element's parent may re-render while it is being passed to
        // other functions, so, we get topic_key first.
        const $topic_row = $(e.target).closest("tr");
        const topic_key = $topic_row.attr("id").slice("recent_conversation:".length);
        const topic_row_index = $topic_row.index();
        focus_clicked_element(topic_row_index, COLUMNS.topic, topic_key);
        window.location.href = $(e.currentTarget).find("a").attr("href");
    });

    // Search for all table rows (this combines stream & topic names)
    $("body").on(
        "keyup",
        "#recent_view_search",
        _.debounce(() => {
            update_filters_view();
            // Wait for user to go idle before initiating search.
        }, 300),
    );

    $("body").on("click", "#recent_view_search_clear", (e) => {
        e.stopPropagation();
        $("#recent_view_search").val("");
        update_filters_view();
    });

    $("body").on("click", ".recent-view-load-more-container .fetch-messages-button", () => {
        maybe_load_older_messages();
        $(".recent-view-load-more-container .button-label").toggleClass("invisible", true);
        $(".recent-view-load-more-container .fetch-messages-button").prop("disabled", true);
        loading.make_indicator(
            $(".recent-view-load-more-container .fetch-messages-button .loading-indicator"),
            {width: 20},
        );
    });

    $(document).on("compose_canceled.zulip", () => {
        if (recent_view_util.is_visible()) {
            revive_current_focus();
        }
    });
}
