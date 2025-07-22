import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import * as typeahead from "../shared/src/typeahead.ts";
import render_introduce_zulip_view_modal from "../templates/introduce_zulip_view_modal.hbs";
import render_recent_view_filters from "../templates/recent_view_filters.hbs";
import render_recent_view_row from "../templates/recent_view_row.hbs";
import render_recent_view_body from "../templates/recent_view_table.hbs";
import render_user_with_status_icon from "../templates/user_with_status_icon.hbs";

import * as activity from "./activity.ts";
import * as blueslip from "./blueslip.ts";
import * as buddy_data from "./buddy_data.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidget} from "./dropdown_widget.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as list_widget from "./list_widget.ts";
import type {ListWidget} from "./list_widget.ts";
import * as loading from "./loading.ts";
import {localstorage} from "./localstorage.ts";
import type {MessageListData} from "./message_list_data.ts";
import * as message_store from "./message_store.ts";
import type {DisplayRecipientUser, Message} from "./message_store.ts";
import * as message_util from "./message_util.ts";
import * as muted_users from "./muted_users.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as recent_senders from "./recent_senders.ts";
import * as recent_view_data from "./recent_view_data.ts";
import type {ConversationData} from "./recent_view_data.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";
import * as views_util from "./views_util.ts";

type Row = {
    last_msg_id: number;
    participated: boolean;
    type: "private" | "stream";
};
let topics_widget: ListWidget<ConversationData, Row> | undefined;
let filters_dropdown_widget: dropdown_widget.DropdownWidget;
export let is_backfill_in_progress = false;
// Sets the number of avatars to display.
// Rest of the avatars, if present, are displayed as {+x}
let max_avatars = 4;
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
export let $current_focus_elem: JQuery | "table" = "table";

// If user clicks a topic in Recent Conversations, then
// we store that topic here so that we can restore focus
// to that topic when user revisits.
let last_visited_topic: string | undefined;
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

let filters = new Set<string>();
let dropdown_filters = new Set<string>();

const recent_conversation_key_prefix = "recent_conversation:";

let is_initial_message_fetch_pending = true;
// We wait for rows to render and restore focus before processing
// any new events.
let is_waiting_for_revive_current_focus = true;
// Used to store the last scroll position of the recent view before
// it is hidden to avoid scroll jumping when it is shown again.
let last_scroll_offset: number | undefined;
let hide_other_views_callback: (() => void) | undefined;

export function set_hide_other_views(callback: () => void): void {
    hide_other_views_callback = callback;
}

export function set_initial_message_fetch_status(value: boolean): void {
    is_initial_message_fetch_pending = value;
}

export function set_backfill_in_progress(value: boolean): void {
    is_backfill_in_progress = value;
    update_load_more_banner();
}

export function clear_for_tests(): void {
    filters.clear();
    dropdown_filters.clear();
    recent_view_data.conversations.clear();
    topics_widget = undefined;
}

export function set_filters_for_tests(new_filters = [views_util.FILTERS.UNMUTED_TOPICS]): void {
    dropdown_filters = new Set(new_filters);
}

export function save_filters(): void {
    ls.set(ls_key, [...filters]);
    ls.set(ls_dropdown_key, [...dropdown_filters]);
}

export function is_in_focus(): boolean {
    // Check if user is focused on Recent Conversations.
    return recent_view_util.is_visible() && views_util.is_in_focus();
}

export function set_default_focus(): void {
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

function set_oldest_message_date(msg_list_data: MessageListData): void {
    const has_found_oldest = msg_list_data.fetch_status.has_found_oldest();
    const has_found_newest = msg_list_data.fetch_status.has_found_newest();
    const oldest_message_in_data = msg_list_data.first_including_muted();
    if (oldest_message_in_data) {
        oldest_message_timestamp = Math.min(
            oldest_message_in_data.timestamp,
            oldest_message_timestamp,
        );
    }

    if (oldest_message_timestamp === Number.POSITIVE_INFINITY && !has_found_oldest) {
        // This should only happen either very early in loading the
        // message list, since it requires the msg_list_data object
        // being empty, without having server confirmation that's the
        // case. Wait for server data to do anything in that
        // situation.
        return;
    }

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
    if ($("#recent-view-content-tbody tr").length > 0) {
        update_load_more_banner();
    }
}

function update_load_more_banner(): void {
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

    const $banner_text = $(".recent-view-load-more-container .last-fetched-message");
    const time_obj = new Date(oldest_message_timestamp * 1000);
    const time_string = timerender.get_localized_date_or_time_for_format(
        time_obj,
        "full_weekday_dayofyear_year_time",
    );
    $banner_text.text($t({defaultMessage: "Showing messages since {time_string}."}, {time_string}));

    if (is_backfill_in_progress) {
        // Keep the button disabled and the loading indicator running
        // until we've finished our recursive backfill.
        return;
    }
    const $button = $(".recent-view-load-more-container .fetch-messages-button");
    const $button_label = $(".recent-view-load-more-container .button-label");
    $button.toggleClass("notvisible", false);

    $button_label.toggleClass("invisible", false);
    $button.prop("disabled", false);
    loading.destroy_indicator(
        $(".recent-view-load-more-container .fetch-messages-button .loading-indicator"),
    );
}

function get_min_load_count(already_rendered_count: number, load_count: number): number {
    const extra_rows_for_viewing_pleasure = 15;
    if (row_focus > already_rendered_count + load_count) {
        return row_focus + extra_rows_for_viewing_pleasure - already_rendered_count;
    }
    return load_count;
}

function is_table_focused(): boolean {
    return $current_focus_elem === "table";
}

function get_row_type(row: number): string {
    // Return "private" or "stream"
    // We use CSS method for finding row type until topics_widget gets initialized.
    if (!topics_widget) {
        const $topic_rows = $("#recent-view-content-tbody tr");
        const $topic_row = $topic_rows.eq(row);
        const is_private = $topic_row.attr("data-private");
        if (is_private) {
            return "private";
        }
        return "stream";
    }

    const current_list = topics_widget.get_current_list();
    const current_row = current_list[row];
    assert(current_row !== undefined);
    return current_row.type;
}

function get_max_selectable_cols(row: number): number {
    // returns maximum number of columns in stream message or direct message row.
    const type = get_row_type(row);
    if (type === "private") {
        return MAX_SELECTABLE_DIRECT_MESSAGE_COLS;
    }
    return MAX_SELECTABLE_TOPIC_COLS;
}

function set_table_focus(row: number, col: number, using_keyboard = false): boolean {
    assert(topics_widget !== undefined);
    if (topics_widget.get_current_list().length === 0) {
        // If there are no topics to show, we don't want to focus on the table.
        set_default_focus();
        return true;
    }

    const $topic_rows = $("#recent-view-content-tbody tr");
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
        const scroll_element = util.the($("html"));
        const half_height_of_visible_area = scroll_element.offsetHeight / 2;
        const topic_offset = topic_offset_to_visible_area($topic_row);

        if (topic_offset === "above") {
            scroll_element.scrollBy({top: -1 * half_height_of_visible_area});
        } else if (topic_offset === "below") {
            scroll_element.scrollBy({top: half_height_of_visible_area});
        }
    }

    let reply_recipient_information: compose_closed_ui.ReplyRecipientInformation;
    if (type === "private") {
        const $recipients_info = $topic_row.find(".recent-view-table-link");
        const narrow_url = $recipients_info.attr("href");
        assert(narrow_url !== undefined);
        const recipient_ids = hash_util.decode_dm_recipient_user_ids_from_narrow_url(narrow_url);
        if (recipient_ids) {
            reply_recipient_information = {
                user_ids: recipient_ids,
            };
        } else {
            reply_recipient_information = {
                display_reply_to: $recipients_info.text(),
            };
        }
    } else {
        const stream_name = $topic_row.find(".recent_topic_stream a").text();
        const stream = stream_data.get_sub_by_name(stream_name);
        reply_recipient_information = {
            stream_id: stream?.stream_id,
            topic: $topic_row.find(".recent_topic_name a").text(),
        };
    }
    compose_closed_ui.update_recipient_text_for_reply_button(reply_recipient_information);
    return true;
}

export function get_focused_row_message(): Message | undefined {
    if (is_table_focused()) {
        assert(topics_widget !== undefined);
        if (topics_widget.get_current_list().length === 0) {
            return undefined;
        }

        const $topic_rows = $("#recent-view-content-tbody tr");
        const $topic_row = $topic_rows.eq(row_focus);
        if ($topic_row.length === 0) {
            // There are less items in the table than `row_focus`.
            // We don't reset `row_focus` here since that is not the
            // purpose of this function.
            return undefined;
        }
        const topic_id = $topic_row.attr("id");
        assert(topic_id !== undefined);
        const conversation_id = topic_id.slice(recent_conversation_key_prefix.length);
        const last_conversation = recent_view_data.conversations.get(conversation_id);
        assert(last_conversation !== undefined);
        const topic_last_msg_id = last_conversation.last_msg_id;
        return message_store.get(topic_last_msg_id);
    }
    return undefined;
}

export function revive_current_focus(): boolean {
    // After re-render, the current_focus_elem is no longer linked
    // to the focused element, this function attempts to revive the
    // link and focus to the element prior to the rerender.

    // We want to set focus on table by default, but we have to wait for
    // initial fetch for rows to appear otherwise focus is set to search input.
    if (is_initial_message_fetch_pending) {
        return false;
    }

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
        assert(topics_widget !== undefined);
        if (last_visited_topic !== undefined) {
            // If the only message in the topic was deleted,
            // then the topic will not be in Recent Conversations data.
            if (recent_view_data.conversations.get(last_visited_topic) !== undefined) {
                const last_conversation = recent_view_data.conversations.get(last_visited_topic);
                assert(last_conversation !== undefined);
                const topic_last_msg_id = last_conversation.last_msg_id;
                const current_list = topics_widget.get_current_list();
                const last_visited_topic_index = current_list.findIndex(
                    (topic) => topic.last_msg_id === topic_last_msg_id,
                );
                if (last_visited_topic_index !== -1) {
                    row_focus = last_visited_topic_index;
                }
            }
            last_visited_topic = undefined;
        }
        set_table_focus(row_focus, col_focus);
        return true;
    }
    assert($current_focus_elem !== "table");
    if ($current_focus_elem.hasClass("dropdown-widget-button")) {
        $("#recent-view-filter_widget").trigger("focus");
        return true;
    }

    const filter_button = $current_focus_elem.attr("data-filter");
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

export function show_loading_indicator(): void {
    $("#recent-view-content-table").hide();
    loading.make_indicator($("#recent_view_loading_messages_indicator"));
}

export function hide_loading_indicator(): void {
    $("#recent-view-content-table").show();
    $("#recent_view_bottom_whitespace").hide();
    loading.destroy_indicator($("#recent_view_loading_messages_indicator"));
}

export function process_messages(
    messages: Message[],
    rows_order_changed = true,
    msg_list_data?: MessageListData,
): void {
    // Always synced with messages in all_messages_data.

    let conversation_data_updated = false;
    const updated_rows = new Set<string>();
    if (messages.length > 0) {
        for (const msg of messages) {
            if (recent_view_data.process_message(msg)) {
                conversation_data_updated = true;
                const key = recent_view_util.get_key_from_message(msg);
                updated_rows.add(key);
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
        if (!rows_order_changed) {
            // If rows order didn't change, we can just rerender the affected rows.
            bulk_inplace_rerender([...updated_rows]);
        } else {
            complete_rerender();
        }
    }
}

function message_to_conversation_unread_count(msg: Message): number {
    if (msg.type === "private") {
        return unread.num_unread_for_user_ids_string(msg.to_user_ids);
    }
    return unread.num_unread_for_topic(msg.stream_id, msg.topic);
}

export function get_pm_tooltip_data(user_ids_string: string): buddy_data.TitleData {
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
                third_line: "",
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

type AvatarsContext = {
    senders: people.SenderInfo[];
    other_sender_names_html: string;
    other_senders_count: number;
};

function get_avatars_context(all_senders: number[]): AvatarsContext {
    // Show the all avatars rather than `max_avatars` + 1.
    const max_space_for_avatars = max_avatars + 1;
    if (all_senders.length <= max_space_for_avatars) {
        return {
            senders: people.sender_info_for_recent_view_row(all_senders),
            other_sender_names_html: "",
            other_senders_count: 0,
        };
    }
    const senders = all_senders.slice(-max_avatars);
    const extra_sender_ids = all_senders.slice(0, -max_avatars);
    const displayed_other_senders = extra_sender_ids.slice(-MAX_EXTRA_SENDERS);
    const other_senders_count = Math.max(0, all_senders.length - max_avatars);
    // Collect extra sender fullname for tooltip
    const displayed_other_names = people.get_display_full_names(displayed_other_senders.reverse());
    if (extra_sender_ids.length > MAX_EXTRA_SENDERS) {
        // We display only 10 extra senders in tooltips,
        // and just display remaining number of senders.
        const remaining_senders = extra_sender_ids.length - MAX_EXTRA_SENDERS;
        // Pluralization syntax from:
        // https://formatjs.github.io/docs/core-concepts/icu-syntax#plural-format
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

    return {
        senders: people.sender_info_for_recent_view_row(senders),
        other_sender_names_html: displayed_other_names.map((name) => _.escape(name)).join("<br />"),
        other_senders_count,
    };
}

type ConversationContext = {
    full_last_msg_date_time: string;
    conversation_key: string;
    unread_count: number;
    last_msg_time: string;
    senders: people.SenderInfo[];
    other_senders_count: number;
    other_sender_names_html: string;
    last_msg_url: string;
    is_spectator: boolean;
} & (
    | {
          is_private: true;
          user_ids_string: string;
          rendered_pm_with: string;
          recipient_id: number;
          pm_url: string;
          is_group: boolean;
          is_bot: boolean;
          user_circle_class: string | undefined;
          has_unread_mention: boolean;
      }
    | {
          is_private: false;
          stream_id: number;
          stream_name: string;
          stream_color: string;
          stream_url: string;
          invite_only: boolean;
          is_web_public: boolean;
          is_archived: boolean;
          topic: string;
          topic_display_name: string;
          is_empty_string_topic: boolean;
          topic_url: string;
          mention_in_unread: boolean;
          visibility_policy: number | false;
          all_visibility_policies: {
              INHERIT: number;
              MUTED: number;
              UNMUTED: number;
              FOLLOWED: number;
          };
      }
);

function format_conversation(conversation_data: ConversationData): ConversationContext {
    const last_msg = message_store.get(conversation_data.last_msg_id);
    assert(last_msg !== undefined);
    const time = new Date(last_msg.timestamp * 1000);
    const type = last_msg.type;
    const full_last_msg_date_time = timerender.get_full_datetime_clarification(time);
    const conversation_key = recent_view_util.get_key_from_message(last_msg);
    const unread_count = message_to_conversation_unread_count(last_msg);
    const last_msg_time = timerender.relative_time_string_from_date(time);
    const is_private = last_msg.type === "private";
    let all_senders;

    let stream_context;
    let dm_context;
    if (type === "stream") {
        // Stream info
        const stream_info = sub_store.get(last_msg.stream_id);
        assert(stream_info !== undefined);
        const stream_id = last_msg.stream_id;
        const stream_name = stream_data.get_stream_name_from_id(last_msg.stream_id);
        const stream_color = stream_info.color;
        const stream_url = hash_util.channel_url_by_user_setting(stream_id);
        const invite_only = stream_info.invite_only;
        const is_web_public = stream_info.is_web_public;
        const is_archived = stream_info.is_archived;
        // Topic info
        const topic = last_msg.topic;
        const topic_display_name = util.get_final_topic_display_name(topic);
        const is_empty_string_topic = topic === "";
        const topic_url = hash_util.by_channel_topic_permalink(stream_id, topic);

        // We hide the row according to filters or if it's muted.
        // We only supply the data to the topic rows and let jquery
        // display / hide them according to filters instead of
        // doing complete re-render.
        const mention_in_unread = unread.topic_has_any_unread_mentions(stream_id, topic);

        const visibility_policy = user_topics.get_topic_visibility_policy(stream_id, topic);
        // The following field is not specific to this context, but this is the
        // easiest way we've figured out for passing the data to the template rendering.
        const all_visibility_policies = user_topics.all_visibility_policies;

        // Since the css for displaying senders in reverse order is much simpler,
        // we provide our handlebars with senders in opposite order.
        // Display in most recent sender first order.
        all_senders = recent_senders.get_topic_recent_senders(stream_id, topic).reverse();

        stream_context = {
            stream_id,
            stream_name,
            stream_color,
            stream_url,
            invite_only,
            is_web_public,
            is_archived,
            topic,
            topic_display_name,
            is_empty_string_topic,
            topic_url,
            mention_in_unread,
            visibility_policy,
            all_visibility_policies,
        };
    } else {
        // Direct message info
        const user_ids_string = last_msg.to_user_ids;
        assert(typeof last_msg.display_recipient !== "string");
        const rendered_pm_with = last_msg.display_recipient
            .filter(
                (recipient: DisplayRecipientUser) =>
                    !people.is_my_user_id(recipient.id) || last_msg.display_recipient.length === 1,
            )
            .map((user: DisplayRecipientUser) =>
                render_user_with_status_icon({
                    name: people.get_display_full_name(user.id),
                    status_emoji_info: user_status.get_status_emoji(user.id),
                }),
            )
            .sort();
        const recipient_id = last_msg.recipient_id;
        const pm_url = last_msg.pm_with_url;
        const is_group = last_msg.display_recipient.length > 2;
        const has_unread_mention =
            unread.num_unread_mentions_for_user_ids_strings(user_ids_string) > 0;

        let is_bot = false;
        let user_circle_class;
        if (!is_group) {
            const user_id = Number.parseInt(last_msg.to_user_ids, 10);
            const is_deactivated = !people.is_active_user_for_popover(user_id);
            const user = people.get_by_user_id(user_id);
            if (user.is_bot) {
                // We display the bot icon rather than a user circle for bots.
                is_bot = true;
            } else {
                user_circle_class = buddy_data.get_user_circle_class(user_id, is_deactivated);
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
        all_senders = recent_senders.get_pm_recent_senders(user_ids_string).participants.reverse();

        dm_context = {
            user_ids_string,
            rendered_pm_with: util.format_array_as_list(rendered_pm_with, "long", "conjunction"),
            recipient_id,
            pm_url,
            is_group,
            is_bot,
            user_circle_class,
            has_unread_mention,
        };
    }

    const shared_context = {
        full_last_msg_date_time,
        conversation_key,
        unread_count,
        last_msg_time,
        last_msg_url: hash_util.by_conversation_and_time_url(last_msg),
        is_spectator: page_params.is_spectator,
        column_indexes: COLUMNS,
        ...get_avatars_context(all_senders),
    };
    if (is_private) {
        assert(dm_context !== undefined);
        return {
            ...shared_context,
            is_private: true,
            ...dm_context,
        };
    }
    assert(stream_context !== undefined);
    return {
        ...shared_context,
        is_private: false,
        ...stream_context,
    };
}

function get_topic_row(topic_data: ConversationData): JQuery {
    const msg = message_store.get(topic_data.last_msg_id);
    assert(msg !== undefined);
    const topic_key = recent_view_util.get_key_from_message(msg);
    return $(`#${CSS.escape(recent_conversation_key_prefix + topic_key)}`);
}

export function process_topic_edit(
    old_stream_id: number,
    old_topic: string,
    new_topic: string,
    new_stream_id: number,
): void {
    // See `recent_senders.process_topic_edit` for
    // logic behind this and important notes on use of this function.
    recent_view_data.conversations.delete(recent_view_util.get_topic_key(old_stream_id, old_topic));

    const old_topic_msgs = message_util.get_loaded_messages_in_topic(old_stream_id, old_topic);
    process_messages(old_topic_msgs);

    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_loaded_messages_in_topic(new_stream_id, new_topic);
    process_messages(new_topic_msgs);
}

export function topic_in_search_results(
    keyword: string,
    stream_name: string,
    topic: string,
): boolean {
    if (keyword === "") {
        return true;
    }
    const topic_display_name = util.get_final_topic_display_name(topic);
    const text = (stream_name + " " + topic_display_name).toLowerCase();
    return typeahead.query_matches_string_in_any_order(keyword, text, " ");
}

export function update_topics_of_deleted_message_ids(message_ids: number[]): void {
    const topics_to_rerender = message_util.get_topics_for_message_ids(message_ids);
    const msgs_to_process = [];
    for (const [stream_id, topic] of topics_to_rerender.values()) {
        recent_view_data.conversations.delete(recent_view_util.get_topic_key(stream_id, topic));
        const msgs = message_util.get_loaded_messages_in_topic(stream_id, topic);
        msgs_to_process.push(...msgs);
    }

    const dm_conversations_to_rerender = new Set<string>();
    for (const msg_id of message_ids) {
        const msg = message_store.get(msg_id);
        if (msg === undefined) {
            continue;
        }

        if (msg.type === "private") {
            const key = recent_view_util.get_key_from_message(msg);
            // Important to assert since we use the key in get_messages_in_dm_conversation.
            assert(key === msg.to_user_ids);
            dm_conversations_to_rerender.add(key);
        }
    }

    for (const key of dm_conversations_to_rerender) {
        recent_view_data.conversations.delete(key);
    }
    if (dm_conversations_to_rerender.size > 0) {
        const dm_messages_to_process = message_util.get_messages_in_dm_conversations(
            dm_conversations_to_rerender,
        );
        msgs_to_process.push(...dm_messages_to_process);
    }

    if (msgs_to_process.length > 0) {
        process_messages(msgs_to_process);
    } else {
        complete_rerender();
    }
}

export function filters_should_hide_row(topic_data: ConversationData): boolean {
    const msg = message_store.get(topic_data.last_msg_id);
    assert(msg !== undefined);

    if (msg.type === "stream") {
        const sub = sub_store.get(msg.stream_id);
        if (!sub?.subscribed && topic_data.type === "stream") {
            // Never try to process deactivated & unsubscribed stream msgs.
            return true;
        }
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

    if (dropdown_filters.has(views_util.FILTERS.UNMUTED_TOPICS) && msg.type === "stream") {
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

    if (filters.has("include_private") && msg.type === "private") {
        const recipients = people.split_to_ints(msg.to_user_ids);

        if (recipients.every((id) => muted_users.is_user_muted(id))) {
            return true;
        }
    }

    if (
        dropdown_filters.has(views_util.FILTERS.FOLLOWED_TOPICS) &&
        msg.type === "stream" &&
        !user_topics.is_topic_followed(msg.stream_id, msg.topic)
    ) {
        return true;
    }

    if (
        dropdown_filters.has(views_util.FILTERS.UNMUTED_TOPICS) &&
        msg.type === "stream" &&
        (user_topics.is_topic_muted(msg.stream_id, msg.topic) ||
            stream_data.is_muted(msg.stream_id)) &&
        !user_topics.is_topic_unmuted_or_followed(msg.stream_id, msg.topic)
    ) {
        return true;
    }

    const search_keyword = $<HTMLInputElement>("#recent_view_search").val();
    assert(search_keyword !== undefined);
    if (msg.type === "stream") {
        const stream_name = stream_data.get_stream_name_from_id(msg.stream_id);
        if (!topic_in_search_results(search_keyword, stream_name, msg.topic)) {
            return true;
        }
    } else {
        assert(msg.type === "private");
        // Display recipient contains user information for DMs.
        assert(typeof msg.display_recipient !== "string");
        const participants = [...msg.display_recipient].map((recipient) =>
            people.get_by_user_id(recipient.id),
        );
        return people.filter_people_by_search_terms(participants, search_keyword).size === 0;
    }

    return false;
}

export function bulk_inplace_rerender(row_keys: string[]): void {
    if (!topics_widget) {
        return;
    }

    // When doing bulk rerender, we assume that order of rows are not going
    // to change by default. Row insertion can still change the order but
    // we ensure the list remains sorted after insertion.
    topics_widget.replace_list_data(get_list_data_for_widget(), false);
    topics_widget.filter_and_sort();
    // Iterate in the order of which the rows should be present so that
    // we are not inserting rows without any rows being present around them.
    for (const topic_data of topics_widget.get_rendered_list()) {
        const msg = message_store.get(topic_data.last_msg_id);
        assert(msg !== undefined);
        const topic_key = recent_view_util.get_key_from_message(msg);
        if (row_keys.includes(topic_key)) {
            inplace_rerender(topic_key, true);
        }
    }
    setTimeout(revive_current_focus, 0);
}

export let inplace_rerender = (topic_key: string, is_bulk_rerender?: boolean): boolean => {
    if (!recent_view_util.is_visible()) {
        return false;
    }
    if (!recent_view_data.conversations.has(topic_key)) {
        return false;
    }

    const topic_data = recent_view_data.conversations.get(topic_key);
    assert(topic_data !== undefined);
    const $topic_row = get_topic_row(topic_data);
    // We cannot rely on `topic_widget.meta.filtered_list` to know
    // if a topic is rendered since the `filtered_list` might have
    // already been updated via other calls.
    const is_topic_rendered = $topic_row.length;
    assert(topics_widget !== undefined);
    if (!is_bulk_rerender) {
        // Resorting the topics_widget is important for the case where we
        // are rerendering because of message editing or new messages
        // arriving, since those operations often change the sort key.
        //
        // NOTE: This doesn't add any new entry to the original list but updates the filtered list
        // based on the current filters and updated row data.
        topics_widget.filter_and_sort();
    }

    const current_topics_list = topics_widget.get_current_list();
    if (is_topic_rendered && filters_should_hide_row(topic_data)) {
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
    } else if (!is_topic_rendered && filters_should_hide_row(topic_data)) {
        // In case `topic_row` is not present, our job is already done here
        // since it has not been rendered yet and we already removed it from
        // the filtered list in `topic_widget`. So, it won't be displayed in
        // the future too.
    } else if (is_topic_rendered && !filters_should_hide_row(topic_data)) {
        // Only a re-render is required in this case.
        topics_widget.render_item(topic_data);
    } else {
        // Final case: !is_topic_rendered && !filters_should_hide_row(topic_data).
        topics_widget.insert_rendered_row(topic_data, () =>
            current_topics_list.findIndex(
                (list_item) => list_item.last_msg_id === topic_data.last_msg_id,
            ),
        );
    }
    if (!is_bulk_rerender) {
        setTimeout(revive_current_focus, 0);
    }
    return true;
};

export function rewire_inplace_rerender(value: typeof inplace_rerender): void {
    inplace_rerender = value;
}

export function update_topic_visibility_policy(stream_id: number, topic: string): boolean {
    const key = recent_view_util.get_topic_key(stream_id, topic);
    if (!recent_view_data.conversations.has(key)) {
        // we receive mute request for a topic we are
        // not tracking currently
        return false;
    }

    inplace_rerender(key);
    return true;
}

export function update_topic_unread_count(message: Message): void {
    const topic_key = recent_view_util.get_key_from_message(message);
    inplace_rerender(topic_key);
}

export function set_filter(filter: string): void {
    // This function updates the `filters` variable
    // after user clicks on one of the filter buttons
    // based on `button-recent-selected` class and current
    // set `filters`.

    // Get the button which was clicked.
    const $filter_elem = $("#recent_view_filter_buttons").find(
        `[data-filter="${CSS.escape(filter)}"]`,
    );

    if ($filter_elem.hasClass("button-recent-selected")) {
        filters.delete(filter);
        // If the button was not selected, we add the filter.
    } else {
        filters.add(filter);
    }

    save_filters();
}

function show_selected_filters(): void {
    // Add `button-recent-selected` to the buttons to show
    // which filters are applied.
    for (const filter of filters) {
        $("#recent_view_filter_buttons")
            .find(`[data-filter="${CSS.escape(filter)}"]`)
            .addClass("button-recent-selected")
            .attr("aria-checked", "true");
    }
}

function get_recent_view_filters_params(): {
    filter_unread: boolean;
    filter_participated: boolean;
    filter_muted: boolean;
    filter_pm: boolean;
    is_spectator: boolean;
} {
    return {
        filter_unread: filters.has("unread"),
        filter_participated: filters.has("participated"),
        filter_muted: filters.has("include_muted"),
        filter_pm: filters.has("include_private"),
        is_spectator: page_params.is_spectator,
    };
}

function setup_dropdown_filters_widget(): void {
    const dropdown_filter = dropdown_filters.values().next();
    assert(dropdown_filter.done === false);
    filters_dropdown_widget = new dropdown_widget.DropdownWidget({
        ...views_util.COMMON_DROPDOWN_WIDGET_PARAMS,
        widget_name: "recent-view-filter",
        item_click_callback: filter_click_handler,
        $events_container: $("#recent_view_filter_buttons"),
        default_id: dropdown_filter.value,
    });
    filters_dropdown_widget.setup();
}

export function update_filters_view(): void {
    const rendered_filters = render_recent_view_filters(get_recent_view_filters_params());
    $("#recent_filters_group").html(rendered_filters);
    show_selected_filters();
    filters_dropdown_widget.render();
    assert(topics_widget !== undefined);
    topics_widget.hard_redraw();
}

function sort_comparator(a: string, b: string): number {
    // compares strings in lowercase and returns -1, 0, 1
    if (a.toLowerCase() > b.toLowerCase()) {
        return 1;
    } else if (a.toLowerCase() === b.toLowerCase()) {
        return 0;
    }
    return -1;
}

function stream_sort(a: Row, b: Row): number {
    if (a.type === b.type) {
        const a_msg = message_store.get(a.last_msg_id);
        assert(a_msg !== undefined);
        const b_msg = message_store.get(b.last_msg_id);
        assert(b_msg !== undefined);

        if (a_msg.type === "stream") {
            assert(b_msg.type === "stream");
            const a_stream_name = stream_data.get_stream_name_from_id(a_msg.stream_id);
            const b_stream_name = stream_data.get_stream_name_from_id(b_msg.stream_id);
            return sort_comparator(a_stream_name, b_stream_name);
        }
        assert(a_msg.type === "private");
        assert(b_msg.type === "private");
        return sort_comparator(a_msg.display_reply_to, b_msg.display_reply_to);
    }
    // if type is not same sort between "private" and "stream"
    return sort_comparator(a.type, b.type);
}

function topic_sort_key(conversation_data: ConversationData): string {
    const message = message_store.get(conversation_data.last_msg_id);
    assert(message !== undefined);
    if (message.type === "private") {
        return message.display_reply_to;
    }
    return message.topic;
}

function topic_sort(a: ConversationData, b: ConversationData): number {
    return sort_comparator(topic_sort_key(a), topic_sort_key(b));
}

function unread_count(conversation_data: ConversationData): number {
    const message = message_store.get(conversation_data.last_msg_id);
    assert(message !== undefined);
    return message_to_conversation_unread_count(message);
}

function unread_sort(a: ConversationData, b: ConversationData): number {
    const a_unread_count = unread_count(a);
    const b_unread_count = unread_count(b);
    if (a_unread_count !== b_unread_count) {
        return a_unread_count - b_unread_count;
    }
    return a.last_msg_id - b.last_msg_id;
}

function topic_offset_to_visible_area($topic_row: JQuery): string | undefined {
    if ($topic_row.length === 0) {
        // TODO: There is a possibility of topic_row being undefined here
        // which logically doesn't makes sense. Find out the case and
        // document it here.
        // We return undefined here since we don't know anything about the
        // topic and the callers will take care of undefined being returned.
        return undefined;
    }

    // Rows are only visible below thead bottom and above compose top.
    const thead_bottom = util.the($("#recent-view-table-headers")).getBoundingClientRect().bottom;
    const compose_top = window.innerHeight - $("#compose").outerHeight(true)!;

    const topic_props = util.the($topic_row).getBoundingClientRect();

    // Topic is above the visible scroll region.
    if (topic_props.top < thead_bottom) {
        return "above";
        // Topic is below the visible scroll region.
    } else if (topic_props.bottom > compose_top) {
        return "below";
    }

    // Topic is visible
    return "visible";
}

function recenter_focus_if_off_screen(): void {
    if (is_waiting_for_revive_current_focus) {
        return;
    }

    const $topic_rows = $("#recent-view-content-tbody tr");
    if (row_focus >= $topic_rows.length) {
        // User used a filter which reduced
        // the number of visible rows.
        return;
    }
    const $topic_row = $topic_rows.eq(row_focus);
    const topic_offset = topic_offset_to_visible_area($topic_row);
    if (topic_offset === undefined) {
        // We don't need to return here since technically topic_offset is not visible.
        blueslip.error("Unable to get topic from row", {row_focus});
    }

    if (topic_offset !== "visible") {
        // Get the element at the center of the table.
        const thead_props = util.the($("#recent-view-table-headers")).getBoundingClientRect();
        const compose_top = window.innerHeight - $("#compose").outerHeight(true)!;
        const topic_center_x = (thead_props.left + thead_props.right) / 2;
        const topic_center_y = (thead_props.bottom + compose_top) / 2;

        const topic_element = document.elementFromPoint(topic_center_x, topic_center_y);
        if (
            topic_element === null ||
            $(topic_element).parents("#recent-view-content-tbody").length === 0
        ) {
            // There are two theoretical reasons that the center
            // element might be null. One is that we haven't rendered
            // the view yet; but in that case, we should have returned
            // early checking is_waiting_for_revive_current_focus.
            //
            // The other possibility is that the table is too short
            // for there to be an topic row element at the center of
            // the table region; in that case, we just select the last
            // element.
            row_focus = $topic_rows.length - 1;
        } else {
            row_focus = $topic_rows.index($(topic_element).closest("tr")[0]);
        }

        set_table_focus(row_focus, col_focus);
    }
}

function callback_after_render(): void {
    // It is important to restore the scroll position as soon
    // as the rendering is complete to avoid scroll jumping.
    if (last_scroll_offset !== undefined) {
        window.scrollTo(0, last_scroll_offset);
    }

    update_load_more_banner();
    setTimeout(() => {
        revive_current_focus();
        is_waiting_for_revive_current_focus = false;
    }, 0);
}

function filter_click_handler(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
    widget: DropdownWidget,
): void {
    event.preventDefault();
    event.stopPropagation();

    if (page_params.is_spectator) {
        // Filter buttons are disabled for spectator.
        return;
    }

    const filter_id = $(event.currentTarget).attr("data-unique-id");
    assert(filter_id !== undefined);
    // We don't support multiple filters yet, so we clear existing and add the new filter.
    dropdown_filters = new Set([filter_id]);
    dropdown.hide();
    widget.render();
    save_filters();

    assert(topics_widget !== undefined);
    topics_widget.hard_redraw();
}

function get_list_data_for_widget(): ConversationData[] {
    return [...recent_view_data.get_conversations().values()];
}

export function complete_rerender(): void {
    if (!recent_view_util.is_visible()) {
        return;
    }

    if (!page_params.is_node_test) {
        max_avatars = Number.parseInt($("html").css("--recent-view-max-avatars"), 10);
    }

    // Show topics list
    const mapped_topic_values = get_list_data_for_widget();

    if (topics_widget) {
        topics_widget.replace_list_data(mapped_topic_values);
        return;
    }

    // This is the first time we are rendering the Recent Conversations view.
    // So, we always scroll to the top to avoid any scroll jumping in case
    // user is returning from another view.
    window.scrollTo(0, 0);

    const rendered_body = render_recent_view_body({
        search_val: $("#recent_view_search").val() ?? "",
        ...get_recent_view_filters_params(),
    });
    $("#recent_view_table").html(rendered_body);

    // `show_selected_filters` needs to be called after the Recent
    // Conversations view has been added to the DOM, to ensure that filters
    // have the correct classes (checked or not) if Recent Conversations
    // was not the first view loaded in the app.
    show_selected_filters();

    const $container = $("#recent-view-content-tbody");
    $container.empty();
    topics_widget = list_widget.create($container, mapped_topic_values, {
        name: "recent_view_table",
        get_item: list_widget.default_get_item,
        $parent_container: $("#recent_view_table"),
        modifier_html(item) {
            return render_recent_view_row(format_conversation(item));
        },
        filter: {
            // We use update_filters_view & filters_should_hide_row to do all the
            // filtering for us, which is called using click_handlers.
            predicate(topic_data) {
                return !filters_should_hide_row(topic_data);
            },
        },
        sort_fields: {
            stream_sort,
            topic_sort,
            unread_sort,
            ...list_widget.generic_sort_functions("numeric", ["last_msg_id"]),
        },
        html_selector: get_topic_row,
        $simplebar_container: $("html"),
        callback_after_render,
        is_scroll_position_for_render: views_util.is_scroll_position_for_render,
        post_scroll__pre_render_callback() {
            // Update the focused element for keyboard navigation if needed.
            recenter_focus_if_off_screen();
        },
        get_min_load_count,
    });
    setup_dropdown_filters_widget();
}

export function update_recent_view_rendered_time(): void {
    if (activity.client_is_active || !recent_view_util.is_visible() || !topics_widget) {
        return;
    }

    // Since we render relative time in recent view, it needs to be
    // updated otherwise it will show stale time. But, we don't want
    // to update it every minute due to performance reasons. So, we
    // only update it when the user comes back from idle which has
    // maximum chance of user seeing incorrect rendered time.
    for (const conversation_data of topics_widget.get_rendered_list()) {
        const last_msg = message_store.get(conversation_data.last_msg_id);
        assert(last_msg !== undefined);
        const time = new Date(last_msg.timestamp * 1000);
        const updated_time = timerender.relative_time_string_from_date(time);
        const $row = get_topic_row(conversation_data);
        const rendered_time = $row.find(".recent_topic_timestamp").text().trim();
        if (updated_time === rendered_time) {
            continue;
        }
        $row.find(".recent_topic_timestamp a").text(updated_time);
    }
}

export function show(): void {
    assert(hide_other_views_callback !== undefined);
    hide_other_views_callback();
    // We remove event handler before hiding, so they need to
    // be attached again, checking for topics_widget to be defined
    // is a reliable solution to check if recent view was displayed earlier.
    const reattach_event_handlers = topics_widget !== undefined;
    views_util.show({
        highlight_view_in_left_sidebar() {
            views_util.handle_message_view_deactivated(
                left_sidebar_navigation_area.highlight_recent_view,
            );
        },
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
    last_scroll_offset = undefined;

    if (reattach_event_handlers) {
        assert(topics_widget !== undefined);
        topics_widget.set_up_event_handlers();
    }

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
            html_submit_button: $t_html({defaultMessage: "Got it"}),
            on_click() {
                /* This widget is purely informational and clicking only closes it. */
            },
            on_hidden() {
                revive_current_focus();
            },
            single_footer_button: true,
            focus_submit_on_open: true,
        });
        onboarding_steps.post_onboarding_step_as_read("intro_recent_view_modal");
    }
}

function filter_buttons(): JQuery {
    return $("#recent_filters_group").children();
}

export function hide(): void {
    if (!recent_view_util.is_visible()) {
        return;
    }
    // Since we have events attached to element (window) which are present in
    // views others than recent view, it is important to clear events here.
    topics_widget?.clear_event_handlers();
    is_waiting_for_revive_current_focus = true;
    last_scroll_offset = window.scrollY;
    views_util.hide({
        $view: $("#recent_view"),
        set_visible: recent_view_util.set_visible,
    });
}

function is_focus_at_last_table_row(): boolean {
    assert(topics_widget !== undefined);
    return row_focus >= topics_widget.get_current_list().length - 1;
}

function has_unread(row: number): boolean {
    assert(topics_widget !== undefined);
    const current_row = topics_widget.get_current_list()[row];
    assert(current_row !== undefined);
    const last_msg_id = current_row.last_msg_id;
    const last_msg = message_store.get(last_msg_id);
    assert(last_msg !== undefined);
    if (last_msg.type === "stream") {
        return unread.num_unread_for_topic(last_msg.stream_id, last_msg.topic) > 0;
    }
    return unread.num_unread_for_user_ids_string(last_msg.to_user_ids) > 0;
}

export function focus_clicked_element(
    topic_row_index: number,
    col: number,
    topic_key?: string,
): void {
    $current_focus_elem = "table";
    col_focus = col;
    row_focus = topic_row_index;

    if (col === COLUMNS.topic) {
        last_visited_topic = topic_key ?? undefined;
    }
    // Set compose_closed_ui reply button text.  The rest of the table
    // focus logic should be a noop.
    set_table_focus(row_focus, col_focus);
}

function left_arrow_navigation(row: number, col: number): void {
    const type = get_row_type(row);

    if (type === "stream" && col === MAX_SELECTABLE_TOPIC_COLS - 1 && !has_unread(row)) {
        col_focus -= 1;
    }

    col_focus -= 1;
    if (col_focus < 0) {
        col_focus = get_max_selectable_cols(row) - 1;
    }
}

function right_arrow_navigation(row: number, col: number): void {
    if (col === 1 && !has_unread(row)) {
        col_focus += 1;
    }

    col_focus += 1;
    if (col_focus >= get_max_selectable_cols(row)) {
        col_focus = 0;
    }
}

function up_arrow_navigation(row: number, col: number): void {
    row_focus -= 1;
    if (row_focus < 0) {
        return;
    }
    const type = get_row_type(row);

    if (type === "stream" && col === 2 && row - 1 >= 0 && !has_unread(row - 1)) {
        col_focus = 1;
    }
}

function down_arrow_navigation(): void {
    row_focus += 1;
}

function get_page_up_down_delta(): number {
    const thead_bottom = util.the($("#recent-view-table-headers")).getBoundingClientRect().bottom;
    const compose_box_top = window.innerHeight - $("#compose").outerHeight(true)!;
    // One usually wants PageDown to move what had been the bottom row
    // to now be at the top, so one can be confident one will see
    // every row using it. This offset helps achieve that goal.
    //
    // See navigate.amount_to_paginate for similar logic in the message feed.
    const scrolling_reduction_to_maintain_context = 75;

    const delta = compose_box_top - thead_bottom - scrolling_reduction_to_maintain_context;
    return delta;
}

function page_up_navigation(): void {
    const delta = get_page_up_down_delta();
    const new_scrollTop = window.scrollY - delta;
    if (new_scrollTop <= 0) {
        row_focus = 0;
        // If we are already at the scroll top, a scroll event
        // is not triggered since the window doesn't actually scroll so
        // we need to update `row_focus` manually.
        if (window.scrollY === 0) {
            set_table_focus(row_focus, col_focus);
            return;
        }
    }

    window.scroll(0, new_scrollTop);
}

function page_down_navigation(): void {
    const delta = get_page_up_down_delta();
    const new_scrollTop = window.scrollY + delta;
    const max_scroll_top = document.body.scrollHeight - window.innerHeight;

    if (new_scrollTop >= max_scroll_top) {
        assert(topics_widget !== undefined);
        row_focus = topics_widget.get_current_list().length - 1;
        // If we are already at the scroll bottom, a scroll event
        // is not triggered since the window doesn't actually scroll so
        // we need to update `row_focus` manually.
        if (window.scrollY === max_scroll_top) {
            set_table_focus(row_focus, col_focus);
            return;
        }
    }

    window.scroll(0, new_scrollTop);
}

function check_row_type_transition(row: number, col: number): boolean {
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

export function change_focused_element($elt: JQuery, input_key: string): boolean {
    // Called from hotkeys.js; like all logic in that module,
    // returning true will cause the caller to do
    // preventDefault/stopPropagation; false will let the browser
    // handle the key.

    if (input_key === "tab" || input_key === "shift_tab") {
        // Tabbing should be handled by browser but to keep the focus element same
        // when we update recent view or user uses other hotkeys, we need to track
        // the current focused element.
        setTimeout(() => {
            const post_tab_focus_elem = document.activeElement;
            if (!(post_tab_focus_elem instanceof HTMLElement)) {
                return;
            }

            if (
                post_tab_focus_elem.id === "recent_view_search" ||
                post_tab_focus_elem.classList.contains("button-recent-filters") ||
                post_tab_focus_elem.classList.contains("dropdown-widget-button")
            ) {
                $current_focus_elem = $(post_tab_focus_elem);
            }

            if ($(post_tab_focus_elem).parents("#recent-view-content-table").length > 0) {
                $current_focus_elem = "table";
                const topic_row_index = $(post_tab_focus_elem).closest("tr").index();
                const col_index = $(post_tab_focus_elem)
                    .closest(".recent_view_focusable")
                    .attr("data-col-index");
                if (!col_index) {
                    return;
                }
                col_focus = Number.parseInt(col_index, 10);
                row_focus = topic_row_index;
            }
        }, 0);
        return false;
    }

    if ($elt.attr("id") === "recent_view_search") {
        // Since the search box a text area, we want the browser to handle
        // Left/Right and selection within the widget; but if the user
        // arrows off the edges, we should move focus to the adjacent widgets..
        const textInput = $<HTMLInputElement>("#recent_view_search").get(0);
        assert(textInput !== undefined);
        const start = textInput.selectionStart!;
        const end = textInput.selectionEnd!;
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
            case "left_arrow":
                if (start !== 0 || is_selected) {
                    return false;
                }
                $current_focus_elem = filter_buttons().last();
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
    } else if ($elt.hasClass("button-recent-filters") || $elt.hasClass("dropdown-widget-button")) {
        switch (input_key) {
            case "click":
                $current_focus_elem = $elt;
                return true;
            case "vim_left":
            case "left_arrow":
                if (filter_buttons().first()[0] === $elt[0]) {
                    $current_focus_elem = $("#recent_view_search");
                } else {
                    $current_focus_elem = $elt.prev();
                }
                break;
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
            case "vim_left":
            case "left_arrow":
                left_arrow_navigation(row_focus, col_focus);
                break;
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
    if ($current_focus_elem !== "table" && input_key !== "escape") {
        $current_focus_elem.trigger("focus");
        if ($current_focus_elem.hasClass("button-recent-filters")) {
            compose_closed_ui.set_standard_text_for_reply_button();
        }
        return true;
    }

    return false;
}

const filter_schema = z._default(z.array(z.string()), []);

function load_filters(): void {
    // load filters from local storage.
    if (!page_params.is_spectator) {
        // A user may have a stored filter and can log out
        // to see web public view. This ensures no filters are
        // selected for spectators.
        const recent_topics = filter_schema.parse(ls.get(ls_key));
        filters = new Set(recent_topics);
        const filter_data = filter_schema.parse(ls.get(ls_dropdown_key));
        dropdown_filters = new Set(filter_data);
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
    hide_other_views,
}: {
    on_click_participant: (avatar_element: Element, participant_user_id: number) => void;
    on_mark_pm_as_read: (user_ids_string: string) => void;
    on_mark_topic_as_read: (stream_id: number, topic: string) => void;
    maybe_load_older_messages: (first_unread_unmuted_message_id: number) => void;
    hide_other_views: () => void;
}): void {
    hide_other_views_callback = hide_other_views;
    load_filters();

    $("body").on(
        "click",
        "#recent-view-content-table .recent_view_participant_avatar",
        function (e) {
            const user_id_string = $(this).parent().attr("data-user-id");
            assert(user_id_string !== undefined);
            const participant_user_id = Number.parseInt(user_id_string, 10);
            e.stopPropagation();
            assert(this instanceof Element);
            on_click_participant(this, participant_user_id);
        },
    );

    $("body").on("click", "#recent_view_search", (e) => {
        e.stopPropagation();
        assert(e.target instanceof HTMLElement);
        change_focused_element($(e.target), "click");
    });

    $("body").on("click", "#recent-view-content-table .on_hover_topic_read", (e) => {
        e.stopPropagation();
        assert(e.currentTarget instanceof HTMLElement);
        const $elt = $(e.currentTarget);
        const topic_row_index = $elt.closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.read);
        const user_ids_string = $elt.attr("data-user-ids-string");
        if (user_ids_string) {
            // direct message row
            on_mark_pm_as_read(user_ids_string);
        } else {
            // Stream row
            const stream_id_string = $elt.attr("data-stream-id");
            assert(stream_id_string !== undefined);
            const stream_id = Number.parseInt(stream_id_string, 10);
            const topic = $elt.attr("data-topic-name");
            assert(topic !== undefined);
            on_mark_topic_as_read(stream_id, topic);
        }
        // If `unread` filter is selected, the focused topic row gets removed
        // and we automatically move one row down.
        if (!filters.has("unread")) {
            change_focused_element($elt, "down_arrow");
        }
    });

    $("body").on("keydown", ".on_hover_topic_read", ui_util.convert_enter_to_click);

    $("body").on("click", ".button-recent-filters", (e) => {
        e.stopPropagation();
        if (page_params.is_spectator) {
            // Filter buttons are disabled for spectator.
            return;
        }

        assert(e.target instanceof HTMLElement);
        change_focused_element($(e.target), "click");
        assert(e.currentTarget instanceof HTMLElement);
        assert(e.currentTarget.dataset.filter !== undefined);
        set_filter(e.currentTarget.dataset.filter);
        update_filters_view();
        revive_current_focus();
    });

    $("body").on("click", "#recent-view-filter_widget", (e) => {
        if (page_params.is_spectator) {
            // Filter buttons are disabled for spectator.
            return;
        }
        assert(e.currentTarget instanceof HTMLElement);
        change_focused_element($(e.currentTarget), "click");
    });

    $("body").on("click", "td.recent_topic_stream", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        e.stopPropagation();
        const topic_row_index = $(e.target).closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.stream);
        window.location.href = $(e.currentTarget).find("a").attr("href")!;
    });

    $("body").on("click", "td.recent_topic_name", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        e.stopPropagation();
        // The element's parent may re-render while it is being passed to
        // other functions, so, we get topic_key first.
        const $topic_row = $(e.target).closest("tr");
        const topic_id = $topic_row.attr("id");
        assert(topic_id !== undefined);
        const topic_key = topic_id.slice("recent_conversation:".length);
        const topic_row_index = $topic_row.index();
        focus_clicked_element(topic_row_index, COLUMNS.topic, topic_key);
        window.location.href = $(e.currentTarget).find("a").attr("href")!;
    });

    $("body").on("click", "#recent-view-content-table .change_visibility_policy", (e) => {
        const topic_row_index = $(e.target).closest("tr").index();
        focus_clicked_element(topic_row_index, COLUMNS.mute);
    });

    // Search for all table rows (this combines stream & topic names)
    $("body").on(
        "input",
        "#recent_view_search",
        _.debounce(() => {
            update_filters_view();
            // Wait for user to go idle before initiating search.
        }, 300),
    );

    $("body").on("click", ".recent-view-load-more-container .fetch-messages-button", () => {
        $(".recent-view-load-more-container .button-label").toggleClass("invisible", true);
        $(".recent-view-load-more-container .fetch-messages-button").prop("disabled", true);
        loading.make_indicator(
            $(".recent-view-load-more-container .fetch-messages-button .loading-indicator"),
            {width: 20},
        );
        maybe_load_older_messages(unread.first_unread_unmuted_message_id);
    });

    $(document).on("compose_canceled.zulip", () => {
        if (recent_view_util.is_visible()) {
            revive_current_focus();
        }
    });
    $(window).on("focus", update_recent_view_rendered_time);
}
