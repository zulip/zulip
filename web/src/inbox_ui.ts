import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_inbox_folder_row from "../templates/inbox_view/inbox_folder_row.hbs";
import render_inbox_folder_with_channels from "../templates/inbox_view/inbox_folder_with_channels.hbs";
import render_inbox_row from "../templates/inbox_view/inbox_row.hbs";
import render_inbox_stream_container from "../templates/inbox_view/inbox_stream_container.hbs";
import render_inbox_view from "../templates/inbox_view/inbox_view.hbs";
import render_introduce_zulip_view_modal from "../templates/introduce_zulip_view_modal.hbs";
import render_user_with_status_icon from "../templates/user_with_status_icon.hbs";

import * as animate from "./animate.ts";
import * as buddy_data from "./buddy_data.ts";
import * as channel_folders from "./channel_folders.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as compose_state from "./compose_state.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {Filter} from "./filter";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as inbox_util from "./inbox_util.ts";
import * as keydown_util from "./keydown_util.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as list_widget from "./list_widget.ts";
import * as loading from "./loading.ts";
import {localstorage} from "./localstorage.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as message_viewport from "./message_viewport.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as people from "./people.ts";
import * as pm_list from "./pm_list.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import * as sub_store from "./sub_store.ts";
import * as topic_list from "./topic_list.ts";
import * as topic_list_data from "./topic_list_data.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import * as user_topics from "./user_topics.ts";
import * as user_topics_ui from "./user_topics_ui.ts";
import * as util from "./util.ts";
import * as views_util from "./views_util.ts";

type DirectMessageContext = {
    conversation_key: string;
    is_direct: boolean;
    rendered_dm_with_html: string;
    is_group: boolean;
    user_circle_class: string | false | undefined;
    is_bot: boolean;
    dm_url: string;
    user_ids_string: string;
    unread_count: number;
    is_hidden: boolean;
    is_collapsed: boolean;
    latest_msg_id: number;
    column_indexes: typeof COLUMNS;
    has_unread_mention: boolean;
};

const direct_message_context_properties: (keyof DirectMessageContext)[] = [
    "conversation_key",
    "is_direct",
    "rendered_dm_with_html",
    "is_group",
    "user_circle_class",
    "is_bot",
    "dm_url",
    "user_ids_string",
    "unread_count",
    "is_hidden",
    "is_collapsed",
    "latest_msg_id",
    "column_indexes",
];

type StreamContext = {
    is_stream: boolean;
    is_archived: boolean;
    invite_only: boolean;
    is_web_public: boolean;
    stream_name: string;
    pin_to_top: boolean;
    is_muted: boolean;
    stream_color: string;
    stream_header_color: string;
    stream_url: string;
    stream_id: number;
    is_hidden: boolean;
    is_collapsed: boolean;
    mention_in_unread: boolean;
    unread_count?: number;
    column_indexes: typeof COLUMNS;
    folder_id: number;
};

const stream_context_properties: (keyof StreamContext)[] = [
    "is_stream",
    "invite_only",
    "is_web_public",
    "stream_name",
    "pin_to_top",
    "is_muted",
    "stream_color",
    "stream_header_color",
    "stream_url",
    "stream_id",
    "is_hidden",
    "is_collapsed",
    "mention_in_unread",
    "unread_count",
    "column_indexes",
];

type TopicContext = {
    is_topic: boolean;
    stream_id: number;
    stream_archived: boolean;
    topic_name: string;
    topic_display_name: string;
    is_empty_string_topic: boolean;
    unread_count: number;
    conversation_key: string;
    topic_url: string;
    is_hidden: boolean;
    is_collapsed: boolean;
    mention_in_unread: boolean;
    latest_msg_id: number;
    all_visibility_policies: typeof user_topics.all_visibility_policies;
    visibility_policy: number | false;
    column_indexes: typeof COLUMNS;
    channel_folder_id?: number;
};

const topic_context_properties: (keyof TopicContext)[] = [
    "is_topic",
    "stream_id",
    "stream_archived",
    "topic_name",
    "topic_display_name",
    "is_empty_string_topic",
    "unread_count",
    "conversation_key",
    "topic_url",
    "is_hidden",
    "is_collapsed",
    "mention_in_unread",
    "latest_msg_id",
    "all_visibility_policies",
    "visibility_policy",
    "column_indexes",
    "channel_folder_id",
];

type ChannelFolderContext = {
    header_id: string;
    is_header_visible: boolean;
    name: string;
    id: number;
    unread_count: number | undefined;
    is_collapsed: boolean;
    has_unread_mention: boolean;
    order: number;
};

const channel_folder_context_properties: (keyof ChannelFolderContext)[] = [
    "header_id",
    "is_header_visible",
    "name",
    "id",
    "unread_count",
    "is_collapsed",
    "has_unread_mention",
];

let dms_dict = new Map<string, DirectMessageContext>();
let topics_dict = new Map<string, Map<string, TopicContext>>();
let streams_dict = new Map<string, StreamContext>();
const OTHER_CHANNELS_FOLDER_ID = -1;
const OTHER_CHANNEL_HEADER_ID = "inbox-channels-no-folder-header";
const CHANNEL_FOLDER_HEADER_ID_PREFIX = "inbox-channel-folder-header-";
const PINNED_CHANNEL_FOLDER_ID = -2;
const PINNED_CHANNEL_HEADER_ID = "inbox-channels-pinned-folder-header";
let channel_folders_dict = new Map<number, ChannelFolderContext>();
let update_triggered_by_user = false;
let filters_dropdown_widget;
let channel_view_topic_widget: InboxTopicListWidget | undefined;

const COLUMNS = {
    FULL_ROW: 0,
    UNREAD_COUNT: 1,
    TOPIC_VISIBILITY: 2,
    ACTION_MENU: 3,
};

const DEFAULT_ROW_FOCUS = 0;
const DEFAULT_COL_FOCUS = COLUMNS.FULL_ROW;

const channel_view_navigation_state = {
    channel_id: -1,
    col_focus: DEFAULT_COL_FOCUS,
    row_focus: DEFAULT_ROW_FOCUS,
    last_scroll_offset: 0,
};

const inbox_view_navigation_state = {
    col_focus: DEFAULT_COL_FOCUS,
    row_focus: DEFAULT_ROW_FOCUS,
    last_scroll_offset: 0,
};

let col_focus = DEFAULT_COL_FOCUS;
let row_focus = DEFAULT_ROW_FOCUS;

let hide_other_views_callback: (() => void) | undefined;

const ls_filter_key = "inbox-filters";
const ls_per_channel_filters_key = "inbox-per-channel-filters";
const ls_collapsed_containers_key = "inbox_collapsed_containers";

const ls = localstorage();
const DEFAULT_FILTER = views_util.FILTERS.UNMUTED_TOPICS;
let filters = new Set([DEFAULT_FILTER]);
const per_channel_filters = new Map<number, Set<string>>();
let collapsed_containers = new Set<string>();

let search_keyword = "";
let inbox_last_search_keyword = "";
const per_channel_last_search_keyword = new Map<number, string>();
const INBOX_SEARCH_ID = "inbox-search";
const INBOX_FILTERS_DROPDOWN_ID = "inbox-filter_widget";
export let current_focus_id: string | undefined;

const STREAM_HEADER_PREFIX = "inbox-stream-header-";
const CONVERSATION_ID_PREFIX = "inbox-row-conversation-";

const LEFT_NAVIGATION_KEYS = ["left_arrow", "vim_left"];
const RIGHT_NAVIGATION_KEYS = ["right_arrow", "vim_right"];

// Used to wait for initial render to complete and set focus
// before we process events like scroll.
let is_waiting_for_revive_current_focus = true;
// Used to store the last scroll position of the inbox before
// it is hidden to avoid scroll jumping when it is shown again.
let last_scroll_offset: number | undefined;

function get_row_from_conversation_key(key: string): JQuery {
    return $(`#${CSS.escape(CONVERSATION_ID_PREFIX + key)}`);
}

function save_data_to_ls(): void {
    ls.set(ls_filter_key, [...filters]);
    ls.set(
        ls_per_channel_filters_key,
        [...per_channel_filters.entries()].map(([channel_id, filter_set]) => [
            channel_id,
            [...filter_set],
        ]),
    );
    ls.set(ls_collapsed_containers_key, [...collapsed_containers]);
}

function save_channel_view_state(): void {
    channel_view_navigation_state.col_focus = col_focus;
    channel_view_navigation_state.row_focus = row_focus;
    channel_view_navigation_state.last_scroll_offset = window.scrollY;
    channel_view_navigation_state.channel_id = inbox_util.get_channel_id();
    per_channel_last_search_keyword.set(channel_view_navigation_state.channel_id, search_keyword);
}

function save_inbox_view_state(): void {
    inbox_view_navigation_state.col_focus = col_focus;
    inbox_view_navigation_state.row_focus = row_focus;
    inbox_view_navigation_state.last_scroll_offset = window.scrollY;
    inbox_last_search_keyword = search_keyword;
}

function restore_channel_view_state(): void {
    const current_channel_id = inbox_util.get_channel_id();
    search_keyword = per_channel_last_search_keyword.get(current_channel_id) ?? "";

    if (channel_view_navigation_state.channel_id === current_channel_id) {
        col_focus = channel_view_navigation_state.col_focus;
        row_focus = channel_view_navigation_state.row_focus;
        last_scroll_offset = channel_view_navigation_state.last_scroll_offset;
        return;
    }

    // Restore default state if channel_id doesn't match.
    col_focus = DEFAULT_COL_FOCUS;
    row_focus = DEFAULT_ROW_FOCUS;
}

function restore_inbox_view_state(): void {
    col_focus = inbox_view_navigation_state.col_focus;
    row_focus = inbox_view_navigation_state.row_focus;
    last_scroll_offset = inbox_view_navigation_state.last_scroll_offset;
    search_keyword = inbox_last_search_keyword;
}

export function show(filter?: Filter): void {
    assert(hide_other_views_callback !== undefined);
    hide_other_views_callback();
    const was_inbox_already_visible = inbox_util.is_visible();

    // Check if we are already narrowed to the same channel view.
    const was_inbox_channel_view = inbox_util.is_channel_view();
    const is_new_filter_channel_view = filter?.is_channel_view();
    if (was_inbox_channel_view && is_new_filter_channel_view) {
        assert(filter !== undefined);
        const filter_channel_id_string = filter.operands("channel")[0];
        assert(filter_channel_id_string !== undefined);
        const filter_channel_id = Number.parseInt(filter_channel_id_string, 10);

        if (inbox_util.get_channel_id() === filter_channel_id) {
            // We expect `update` to handle any live updates such that we don't need
            // do anything here if view for the same channel is visible.
            return;
        }
    } else if (was_inbox_already_visible && !was_inbox_channel_view && is_new_filter_channel_view) {
        save_inbox_view_state();
    }

    if (was_inbox_already_visible && was_inbox_channel_view) {
        save_channel_view_state();
    }

    // Before we set the filter, we need to check if the inbox view is already visible.
    const normal_inbox_view_is_visible = inbox_util.is_visible() && !was_inbox_channel_view;

    inbox_util.set_filter(filter);
    if (inbox_util.is_channel_view()) {
        restore_channel_view_state();
        views_util.show({
            highlight_view_in_left_sidebar() {
                assert(filter !== undefined);
                left_sidebar_navigation_area.handle_narrow_activated(filter);
                stream_list.handle_narrow_activated(filter, false, false);
                pm_list.handle_narrow_activated(filter);
            },
            $view: $("#inbox-view"),
            update_compose: compose_closed_ui.update_buttons,
            // We already did a check above for that.
            is_visible: () => false,
            set_visible: inbox_util.set_visible,
            complete_rerender,
            is_recent_view: false,
        });
        return;
    }

    restore_inbox_view_state();
    views_util.show({
        highlight_view_in_left_sidebar() {
            views_util.handle_message_view_deactivated(
                left_sidebar_navigation_area.highlight_inbox_view,
            );
        },
        $view: $("#inbox-view"),
        update_compose: compose_closed_ui.update_buttons,
        is_visible: () => normal_inbox_view_is_visible,
        set_visible: inbox_util.set_visible,
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
            html_heading: $t_html({defaultMessage: "Welcome to your inbox!"}),
            html_body,
            html_submit_button: $t_html({defaultMessage: "Got it"}),
            on_click() {
                // Do nothing
            },
            on_hidden() {
                revive_current_focus();
            },
            single_footer_button: true,
            focus_submit_on_open: true,
        });
        onboarding_steps.post_onboarding_step_as_read("intro_inbox_view_modal");
    }
}

export function hide(): void {
    if (!inbox_util.is_visible()) {
        return;
    }

    is_waiting_for_revive_current_focus = true;
    if (inbox_util.is_channel_view()) {
        save_channel_view_state();
    } else {
        save_inbox_view_state();
    }

    views_util.hide({
        $view: $("#inbox-view"),
        set_visible: inbox_util.set_visible,
    });

    inbox_util.set_filter(undefined);
}

function get_topic_key(stream_id: number, topic: string): string {
    return stream_id + ":" + topic;
}

function get_stream_key(stream_id: number): string {
    return "stream_" + stream_id;
}

function get_stream_container(stream_key: string): JQuery {
    return $(`#${CSS.escape(stream_key)}`);
}

function get_stream_header_row(stream_id: number): JQuery {
    const $stream_header_row = $(`#${CSS.escape(STREAM_HEADER_PREFIX + stream_id)}`);
    return $stream_header_row;
}

function load_data_from_ls(): void {
    const saved_filters = new Set(z.optional(z.array(z.string())).parse(ls.get(ls_filter_key)));
    const valid_filters = new Set(Object.values(views_util.FILTERS));
    // If saved filters are not in the list of valid filters, we reset to default.
    const is_subset = [...saved_filters].every((filter) => valid_filters.has(filter));
    if (saved_filters.size === 0 || !is_subset) {
        filters = new Set([views_util.FILTERS.UNMUTED_TOPICS]);
    } else {
        filters = saved_filters;
    }
    collapsed_containers = new Set(
        z.optional(z.array(z.string())).parse(ls.get(ls_collapsed_containers_key)),
    );
    const saved_per_channel_filters = z
        .optional(z.array(z.tuple([z.number(), z.array(z.string())])))
        .parse(ls.get(ls_per_channel_filters_key));
    for (const [channel_id, filter_set] of saved_per_channel_filters ?? []) {
        const valid_filter_set = new Set(filter_set.filter((filter) => valid_filters.has(filter)));
        if (valid_filter_set.size > 0) {
            per_channel_filters.set(channel_id, valid_filter_set);
        }
    }
}

function format_dm(
    user_ids_string: string,
    unread_count: number,
    latest_msg_id: number,
): DirectMessageContext {
    const recipient_ids = people.user_ids_string_to_ids_array(user_ids_string);
    if (recipient_ids.length === 0) {
        // Self DM
        recipient_ids.push(people.my_current_user_id());
    }

    const rendered_dm_with_html = recipient_ids
        .map((recipient_id) => ({
            name: people.get_display_full_name(recipient_id),
            status_emoji_info: user_status.get_status_emoji(recipient_id),
        }))
        .toSorted((a, b) => util.strcmp(a.name, b.name))
        .map((user_info) => render_user_with_status_icon(user_info));

    let user_circle_class: string | false | undefined;
    let is_bot = false;
    if (recipient_ids.length === 1 && recipient_ids[0] !== undefined) {
        const user_id = recipient_ids[0];
        const is_deactivated = !people.is_active_user_for_popover(user_id);
        is_bot = people.get_by_user_id(user_id).is_bot;
        user_circle_class = is_bot
            ? false
            : buddy_data.get_user_circle_class(recipient_ids[0], is_deactivated);
    }
    const has_unread_mention = unread.num_unread_mentions_for_user_ids_strings(user_ids_string) > 0;

    const context = {
        conversation_key: user_ids_string,
        is_direct: true,
        rendered_dm_with_html: util.format_array_as_list_with_conjunction(
            rendered_dm_with_html,
            "long",
        ),
        is_group: recipient_ids.length > 1,
        user_circle_class,
        is_bot,
        dm_url: hash_util.pm_with_url(user_ids_string),
        user_ids_string,
        unread_count,
        is_hidden: filter_should_hide_dm_row({dm_key: user_ids_string}),
        is_collapsed: collapsed_containers.has("inbox-dm-header"),
        latest_msg_id,
        column_indexes: COLUMNS,
        has_unread_mention,
    };

    return context;
}

function insert_dms(keys_to_insert: string[]): void {
    const sorted_keys = [...dms_dict.keys()];
    // If we need to insert at the top, we do it separately to avoid edge case in loop below.
    if (sorted_keys[0] !== undefined && keys_to_insert.includes(sorted_keys[0])) {
        $("#inbox-direct-messages-container").prepend(
            $(render_inbox_row(dms_dict.get(sorted_keys[0]))),
        );
    }

    for (const [i, key] of sorted_keys.entries()) {
        if (i === 0) {
            continue;
        }

        if (keys_to_insert.includes(key)) {
            const $previous_row = get_row_from_conversation_key(sorted_keys[i - 1]!);
            $previous_row.after($(render_inbox_row(dms_dict.get(key))));
        }
    }
}

function rerender_dm_inbox_row_if_needed(
    new_dm_data: DirectMessageContext,
    old_dm_data: DirectMessageContext | undefined,
    dm_keys_to_insert: string[],
): void {
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
    for (const property of direct_message_context_properties) {
        if (new_dm_data[property] !== old_dm_data[property]) {
            const $rendered_row = get_row_from_conversation_key(new_dm_data.conversation_key);
            $rendered_row.replaceWith($(render_inbox_row(new_dm_data)));
            return;
        }
    }
}

function get_channel_folder_id(info: {folder_id: number | null; is_pinned: boolean}): number {
    if (info.is_pinned) {
        return PINNED_CHANNEL_FOLDER_ID;
    }
    if (info.folder_id === null) {
        return OTHER_CHANNELS_FOLDER_ID;
    }
    if (!user_settings.web_inbox_show_channel_folders) {
        return OTHER_CHANNELS_FOLDER_ID;
    }
    return info.folder_id;
}

function format_stream(stream_id: number): StreamContext {
    // NOTE: Unread count is not included in this function as it is more
    // efficient for the callers to calculate it based on filters.
    const stream_info = sub_store.get(stream_id);
    assert(stream_info !== undefined);

    return {
        is_stream: true,
        is_archived: stream_info.is_archived,
        invite_only: stream_info.invite_only,
        is_web_public: stream_info.is_web_public,
        stream_name: stream_info.name,
        pin_to_top: stream_info.pin_to_top,
        is_muted: stream_info.is_muted,
        folder_id: get_channel_folder_id({
            folder_id: stream_info.folder_id,
            is_pinned: stream_info.pin_to_top,
        }),
        stream_color: stream_color.get_stream_privacy_icon_color(stream_info.color),
        stream_header_color: stream_color.get_recipient_bar_color(stream_info.color),
        stream_url: hash_util.channel_url_by_user_setting(stream_id),
        stream_id,
        // Will be displayed if any topic is visible.
        is_hidden: true,
        is_collapsed: collapsed_containers.has(STREAM_HEADER_PREFIX + stream_id),
        mention_in_unread: unread.stream_has_any_unread_mentions(stream_id),
        column_indexes: COLUMNS,
    };
}

function update_stream_data(
    stream_id: number,
    stream_key: string,
    topic_dict: Map<string, {topic_count: number; latest_msg_id: number}>,
): void {
    const stream_topics_data = new Map<string, TopicContext>();
    const stream_data = format_stream(stream_id);
    const stream_archived = stream_data.is_archived;
    let stream_post_filter_unread_count = 0;
    for (const [topic, {topic_count, latest_msg_id}] of topic_dict) {
        const topic_key = get_topic_key(stream_id, topic);
        if (topic_count) {
            const topic_data = format_topic(
                stream_id,
                stream_archived,
                topic,
                topic_count,
                latest_msg_id,
            );
            stream_topics_data.set(topic_key, topic_data);
            if (!topic_data.is_hidden) {
                stream_post_filter_unread_count += topic_data.unread_count;
            }
        }
    }
    topics_dict.set(stream_key, get_sorted_row_dict(stream_topics_data));
    stream_data.is_hidden = stream_post_filter_unread_count === 0;
    stream_data.unread_count = stream_post_filter_unread_count;
    streams_dict.set(stream_key, stream_data);
}

function rerender_stream_inbox_header_if_needed(
    new_stream_data: StreamContext,
    old_stream_data: StreamContext,
): void {
    for (const property of stream_context_properties) {
        if (new_stream_data[property] !== old_stream_data[property]) {
            const $rendered_row = get_stream_header_row(new_stream_data.stream_id);
            $rendered_row.replaceWith($(render_inbox_row(new_stream_data)));
            return;
        }
    }
}

function get_channel_folder_header_id(folder_id: number): string {
    if (folder_id === OTHER_CHANNELS_FOLDER_ID) {
        return OTHER_CHANNEL_HEADER_ID;
    } else if (folder_id === PINNED_CHANNEL_FOLDER_ID) {
        return PINNED_CHANNEL_HEADER_ID;
    }
    return CHANNEL_FOLDER_HEADER_ID_PREFIX + folder_id;
}

function rerender_channel_folder_header_if_needed(
    old_folder_data: ChannelFolderContext,
    new_folder_data: ChannelFolderContext,
): void {
    for (const property of channel_folder_context_properties) {
        if (new_folder_data[property] !== old_folder_data[property]) {
            const $rendered_row = $(`#${get_channel_folder_header_id(new_folder_data.id)}`);
            $rendered_row.replaceWith($(render_inbox_folder_row(new_folder_data)));
            return;
        }
    }
}

function format_topic(
    stream_id: number,
    stream_archived: boolean,
    topic: string,
    topic_unread_count: number,
    latest_msg_id: number,
    is_channel_view = false,
): TopicContext {
    const common_context = {
        is_topic: true,
        stream_id,
        stream_archived,
        topic_name: topic,
        topic_display_name: util.get_final_topic_display_name(topic),
        is_empty_string_topic: topic === "",
        unread_count: topic_unread_count,
        conversation_key: get_topic_key(stream_id, topic),
        topic_url: hash_util.by_channel_topic_permalink(stream_id, topic),
        latest_msg_id,
        mention_in_unread: unread.topic_has_any_unread_mentions(stream_id, topic),
        // The 'all_visibility_policies' field is not specific to this context,
        // but this is the easiest way we've figured out for passing the data
        // to the template rendering.
        all_visibility_policies: user_topics.all_visibility_policies,
        visibility_policy: user_topics.get_topic_visibility_policy(stream_id, topic),
        column_indexes: COLUMNS,
    };

    if (is_channel_view) {
        return {
            ...common_context,
            // We use TopicListWidget to check which topics to show so
            // that `update` works correctly. So we're not using the
            // inbox_ui filtering/hiding logic here.
            is_hidden: false,
            // Inbox view setting for collapsed containers is not
            // relevant in the single-channel view.
            is_collapsed: false,
        };
    }

    return {
        ...common_context,
        is_hidden: filter_should_hide_stream_row({stream_id, topic}),
        is_collapsed: collapsed_containers.has(STREAM_HEADER_PREFIX + stream_id),
    };
}

function insert_stream(stream_key: string): void {
    const channel_folder_id = streams_dict.get(stream_key)!.folder_id;
    const sorted_stream_keys = get_sorted_stream_keys(channel_folder_id);
    const stream_index = sorted_stream_keys.indexOf(stream_key);
    const rendered_stream = render_inbox_stream_container({
        topics_dict: new Map([[stream_key, topics_dict.get(stream_key)]]),
        streams_dict,
    });
    const $channel_folder_header = $(`#${get_channel_folder_header_id(channel_folder_id)}`);
    if (stream_index === 0) {
        $channel_folder_header.next(".inbox-folder-components").prepend($(rendered_stream));
    } else {
        const previous_stream_key = sorted_stream_keys[stream_index - 1]!;
        $(rendered_stream).insertAfter(get_stream_container(previous_stream_key));
    }
}

function insert_topics(keys: string[], stream_key: string): void {
    const stream_topics_data = topics_dict.get(stream_key);
    assert(stream_topics_data !== undefined);
    const sorted_keys = [...stream_topics_data.keys()];
    // If we need to insert at the top, we do it separately to avoid edge case in loop below.
    if (sorted_keys[0] !== undefined && keys.includes(sorted_keys[0])) {
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
            const $previous_row = get_row_from_conversation_key(sorted_keys[i - 1]!);
            $previous_row.after($(render_inbox_row(stream_topics_data.get(key))));
        }
    }
}

function rerender_topic_inbox_row_if_needed(
    new_topic_data: TopicContext,
    old_topic_data: TopicContext | undefined,
    topic_keys_to_insert: string[],
): void {
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

    for (const property of topic_context_properties) {
        if (new_topic_data[property] !== old_topic_data[property]) {
            const $rendered_row = get_row_from_conversation_key(new_topic_data.conversation_key);
            $rendered_row.replaceWith($(render_inbox_row(new_topic_data)));
            return;
        }
    }
}

function get_sorted_stream_keys(channel_folder_id: number | undefined = undefined): string[] {
    function compare_function(a: string, b: string): number {
        const stream_a = streams_dict.get(a);
        const stream_b = streams_dict.get(b);
        assert(stream_a !== undefined && stream_b !== undefined);

        if (channel_folder_id !== undefined) {
            // Sort streams not in the folder to the end.
            if (stream_a.folder_id !== channel_folder_id) {
                return 1;
            }
            if (stream_b.folder_id !== channel_folder_id) {
                return -1;
            }
        }

        // The muted stream is sorted lower.
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

    return [...topics_dict.keys()].toSorted(compare_function);
}

function get_sorted_stream_topic_dict(): Map<string, Map<string, TopicContext>> {
    const sorted_stream_keys = get_sorted_stream_keys();
    const sorted_topic_dict = new Map<string, Map<string, TopicContext>>();
    for (const sorted_stream_key of sorted_stream_keys) {
        sorted_topic_dict.set(sorted_stream_key, topics_dict.get(sorted_stream_key)!);
    }

    return sorted_topic_dict;
}

function get_sorted_row_dict<T extends DirectMessageContext | TopicContext>(
    row_dict: Map<string, T>,
): Map<string, T> {
    return new Map([...row_dict].toSorted(([, a], [, b]) => b.latest_msg_id - a.latest_msg_id));
}

function sort_channel_folders(): void {
    const sorted_channel_folders = [...channel_folders_dict.values()];
    sorted_channel_folders.sort((a, b) => {
        // Sort OTHER_CHANNELS_FOLDER_ID last, then by order with PINNED_CHANNEL_FOLDER_ID first.
        if (a.id === OTHER_CHANNELS_FOLDER_ID) {
            return 1;
        }
        if (b.id === OTHER_CHANNELS_FOLDER_ID) {
            return -1;
        }
        if (a.id === PINNED_CHANNEL_FOLDER_ID) {
            return -1;
        }
        if (b.id === PINNED_CHANNEL_FOLDER_ID) {
            return 1;
        }
        return a.order - b.order;
    });

    channel_folders_dict = new Map(sorted_channel_folders.map((folder) => [folder.id, folder]));
}

function get_folder_name_from_id(folder_id: number): string {
    if (folder_id === PINNED_CHANNEL_FOLDER_ID) {
        return $t({defaultMessage: "PINNED CHANNELS"});
    }

    if (folder_id === OTHER_CHANNELS_FOLDER_ID) {
        if (channel_folders_dict.get(OTHER_CHANNELS_FOLDER_ID)?.name !== undefined) {
            // To avoid unnecessary UI updates, we return the existing name as we
            // update the name at the end when we have data for all the channels.
            // See `update_name_of_other_channels_folder`.
            return channel_folders_dict.get(OTHER_CHANNELS_FOLDER_ID)!.name;
        }
        return $t({defaultMessage: "OTHER CHANNELS"});
    }

    return channel_folders.get_channel_folder_by_id(folder_id).name;
}

function get_folder_order_from_id(folder_id: number): number {
    if (folder_id === PINNED_CHANNEL_FOLDER_ID || folder_id === OTHER_CHANNELS_FOLDER_ID) {
        return 0;
    }

    return channel_folders.get_channel_folder_by_id(folder_id).order;
}

function update_channel_folder_data(channel_context: StreamContext): void {
    const folder_id = channel_context.folder_id;
    const folder_header_id = get_channel_folder_header_id(folder_id);
    let folder_context = channel_folders_dict.get(folder_id);
    if (folder_context === undefined) {
        folder_context = {
            id: folder_id,
            header_id: folder_header_id,
            name: get_folder_name_from_id(folder_id),
            is_header_visible: !channel_context.is_hidden,
            unread_count: channel_context.unread_count,
            is_collapsed: collapsed_containers.has(folder_header_id),
            has_unread_mention: channel_context.mention_in_unread,
            order: get_folder_order_from_id(folder_id),
        };
        channel_folders_dict.set(folder_id, folder_context);
    } else {
        folder_context.unread_count =
            (folder_context.unread_count ?? 0) + (channel_context.unread_count ?? 0);
        folder_context.is_header_visible =
            folder_context.is_header_visible || !channel_context.is_hidden;
        folder_context.has_unread_mention =
            folder_context.has_unread_mention || channel_context.mention_in_unread;
    }
}

function update_name_of_other_channels_folder({
    should_update_ui,
}: {
    should_update_ui: boolean;
}): void {
    // Update name of OTHER_CHANNELS_FOLDER_ID in case
    // `is_other_channels_only_visible_folder` changed.
    const other_channels_folder = channel_folders_dict.get(OTHER_CHANNELS_FOLDER_ID);
    if (other_channels_folder !== undefined) {
        let updated_name = $t({defaultMessage: "OTHER CHANNELS"});
        if (is_other_channels_only_visible_folder()) {
            updated_name = $t({defaultMessage: "CHANNELS"});
        }

        if (other_channels_folder.name === updated_name) {
            // No changes needed.
            return;
        }

        other_channels_folder.name = updated_name;
    }

    if (should_update_ui) {
        const $other_channels_folder_header = $(
            `#${CSS.escape(get_channel_folder_header_id(OTHER_CHANNELS_FOLDER_ID))}`,
        );
        if ($other_channels_folder_header.length > 0) {
            $other_channels_folder_header
                .find(".inbox-header-name-text")
                .text(other_channels_folder!.name);
        }
    }
}

function reset_data(): {
    unread_dms_count: number;
    is_dms_collapsed: boolean;
    has_dms_post_filter: boolean;
    has_visible_unreads: boolean;
    has_unread_mention: boolean;
} {
    dms_dict = new Map();
    topics_dict = new Map();
    streams_dict = new Map();
    channel_folders_dict = new Map();

    const unread_dms = unread.get_unread_pm();
    const unread_dms_count = unread_dms.total_count;
    const unread_dms_dict = unread_dms.pm_dict;
    const has_unread_mention = unread.num_unread_mentions_in_dms() > 0;

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
                if (!streams_dict.get(stream_key)!.is_hidden) {
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

    for (const [, channel_context] of streams_dict) {
        update_channel_folder_data(channel_context);
    }

    update_name_of_other_channels_folder({
        should_update_ui: false,
    });

    sort_channel_folders();

    return {
        has_unread_mention,
        unread_dms_count,
        is_dms_collapsed,
        has_dms_post_filter,
        has_visible_unreads,
    };
}

function is_other_channels_only_visible_folder(): boolean {
    const visible_channel_folders = channel_folders_dict
        .values()
        .filter((folder) => folder.is_header_visible)
        .toArray();

    if (visible_channel_folders.length !== 1) {
        return false;
    }

    const only_visible_folder = visible_channel_folders[0]!;
    return only_visible_folder.id === OTHER_CHANNELS_FOLDER_ID;
}

function show_empty_inbox_text(has_visible_unreads: boolean): void {
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

function filter_click_handler(
    event: JQuery.TriggeredEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
): void {
    event.preventDefault();
    event.stopPropagation();

    const filter_id = $(event.currentTarget).attr("data-unique-id");
    assert(filter_id !== undefined);
    // We don't support multiple filters yet, so we clear existing and add the new filter.
    if (inbox_util.is_channel_view()) {
        const channel_id = inbox_util.get_channel_id();
        per_channel_filters.set(channel_id, new Set([filter_id]));
    } else {
        filters = new Set([filter_id]);
    }
    save_data_to_ls();
    dropdown.hide();
    widget.render();
    update();
}

export function update_channel_view(channel_id: number): void {
    if (
        inbox_util.is_visible() &&
        inbox_util.is_channel_view() &&
        inbox_util.get_channel_id() === channel_id
    ) {
        channel_view_topic_widget?.build();
    }
}

function show_empty_inbox_channel_view_text(is_empty: boolean): void {
    if (is_empty) {
        $("#inbox-list").css("border-width", "0");
        if (search_keyword) {
            $("#inbox-empty-channel-view-with-search").show();
            $("#inbox-empty-channel-view-without-search").hide();
        } else {
            $("#inbox-empty-channel-view-with-search").hide();
            $("#inbox-empty-channel-view-without-search").show();
        }
    } else {
        $("#inbox-empty-channel-view-with-search").hide();
        $("#inbox-empty-channel-view-without-search").hide();
        $("#inbox-list").css("border-width", "1px");
    }
}

function get_min_load_count(already_rendered_count: number, load_count: number): number {
    // Height of inbox row is ~28px at 16px = 1.75rem and we want this render to fill the entire view height.
    const view_height = message_viewport.height();
    const row_height = 1.75 * user_settings.web_font_size_px;
    const extra_rows_for_viewing_pleasure = view_height / row_height;
    const ideal_rendered_rows_count = row_focus + extra_rows_for_viewing_pleasure;
    if (ideal_rendered_rows_count > already_rendered_count + load_count) {
        return ideal_rendered_rows_count - already_rendered_count;
    }
    return load_count;
}

function show_channel_view_loading_indicator(): void {
    $("#inbox-loading-indicator .bottom-messages-logo").show();
    loading.make_indicator($("#inbox-loading-indicator #loading_more_indicator"), {
        abs_positioned: true,
    });
}

function hide_channel_view_loading_indicator(): void {
    $("#inbox-loading-indicator .bottom-messages-logo").hide();
    loading.destroy_indicator($("#inbox-loading-indicator #loading_more_indicator"));
}

class InboxTopicListWidget extends topic_list.TopicListWidget {
    override topic_list_class_name = "inbox-channel-topic-list";
    topics_widget?: list_widget.ListWidget<topic_list_data.TopicInfo>;

    override build(): this {
        // Hide any existing loading indicators.
        hide_channel_view_loading_indicator();
        const is_zoomed = true;
        const $container = $("#inbox-list");
        const list_info = topic_list_data.get_list_info(
            this.my_stream_id,
            is_zoomed,
            this.filter_topics,
        );

        const all_topics = list_info.items;
        this.topics_widget = list_widget.create($container, all_topics, {
            name: "inbox-channel-topics-list",
            get_item: list_widget.default_get_item,
            $parent_container: $("#inbox-view"),
            modifier_html(item) {
                const topic_context = format_topic(
                    item.stream_id,
                    false,
                    item.topic_name,
                    item.unread,
                    -1,
                    true,
                );
                return render_inbox_row(topic_context);
            },
            $simplebar_container: $(":root"),
            is_scroll_position_for_render: views_util.is_scroll_position_for_render,
            get_min_load_count,
        });

        if (!stream_topic_history.has_history_for(this.my_stream_id)) {
            show_channel_view_loading_indicator();
            stream_topic_history_util.get_server_history(this.my_stream_id, () => {
                if (channel_view_topic_widget?.get_stream_id() !== this.my_stream_id) {
                    return;
                }

                channel_view_topic_widget.build();
                // Also, update the left sidebar topics list for this channel.
                topic_list.update_widget_for_stream(this.my_stream_id);
            });
        } else {
            show_empty_inbox_channel_view_text(this.is_empty());
        }
        setTimeout(() => {
            revive_current_focus();
        }, 0);
        return this;
    }

    override is_empty(): boolean {
        if (this.topics_widget === undefined) {
            return true;
        }
        return this.topics_widget.get_current_list().length === 0;
    }
}

function filter_topics_in_channel(channel_id: number, topics: string[]): string[] {
    return topics.filter((topic) => !filter_should_hide_stream_row({stream_id: channel_id, topic}));
}

function render_channel_view(channel_id: number): void {
    $("#inbox-pane").html(
        render_inbox_view({
            normal_view: false,
            search_val: search_keyword,
            INBOX_SEARCH_ID,
            show_channel_folder_toggle: channel_folders.user_has_folders(),
        }),
    );
    // Hide any empty inbox text by default.
    show_empty_inbox_text(true);
    channel_view_topic_widget = new InboxTopicListWidget(
        $("#inbox-list"),
        channel_id,
        (topic_names: string[]) => filter_topics_in_channel(channel_id, topic_names),
    );
    channel_view_topic_widget.build();
}

function inbox_view_dropdown_options(
    current_value: string | number | undefined,
): dropdown_widget.Option[] {
    return views_util.filters_dropdown_options(current_value, inbox_util.is_channel_view());
}

export function complete_rerender(coming_from_other_views = false): void {
    if (!inbox_util.is_visible()) {
        return;
    }
    load_data_from_ls();

    // To avoid user scrolling before we have completed the rendering,
    // Wrap the rendering and position restoration in a requestAnimationFrame.
    requestAnimationFrame(() => {
        let first_filter: IteratorResult<string>;
        if (inbox_util.is_channel_view()) {
            const channel_id = inbox_util.get_channel_id();
            assert(channel_id !== undefined);

            if (channel_view_topic_widget?.get_stream_id() === channel_id) {
                channel_view_topic_widget.build();
            } else {
                // Show unknown channel message if we don't have data for channel.
                if (!stream_data.get_sub_by_id(channel_id)) {
                    $("#inbox-pane").html(
                        render_inbox_view({
                            unknown_channel: true,
                            show_channel_folder_toggle: channel_folders.user_has_folders(),
                        }),
                    );
                    return;
                }

                render_channel_view(channel_id);
            }
            const channel_filter = per_channel_filters.get(channel_id) ?? new Set([DEFAULT_FILTER]);
            first_filter = channel_filter.values().next();
        } else {
            channel_view_topic_widget = undefined;
            const {has_visible_unreads, ...additional_context} = reset_data();
            $("#inbox-pane").html(
                render_inbox_view({
                    normal_view: true,
                    search_val: search_keyword,
                    INBOX_SEARCH_ID,
                    dms_dict,
                    topics_dict,
                    streams_dict,
                    channel_folders_dict,
                    show_channel_folder_toggle: channel_folders.user_has_folders(),
                    ...additional_context,
                }),
            );
            show_empty_inbox_channel_view_text(false);
            show_empty_inbox_text(has_visible_unreads);
            first_filter = filters.values().next();
        }

        if (coming_from_other_views) {
            if (last_scroll_offset !== undefined) {
                // It is important to restore the scroll position as soon
                // as the rendering is complete to avoid scroll jumping.
                window.scrollTo(0, last_scroll_offset);
            } else {
                // If the focus is not on the inbox rows, the inbox view scrolls
                // down when moving from other views to the inbox view. To avoid
                // this, we scroll to top before restoring focus via revive_current_focus.
                window.scrollTo(0, 0);
            }
        }

        revive_current_focus();
        is_waiting_for_revive_current_focus = false;

        filters_dropdown_widget = new dropdown_widget.DropdownWidget({
            ...views_util.COMMON_DROPDOWN_WIDGET_PARAMS,
            widget_name: "inbox-filter",
            item_click_callback: filter_click_handler,
            $events_container: $("#inbox-main"),
            default_id: first_filter.done ? DEFAULT_FILTER : first_filter.value,
            get_options: inbox_view_dropdown_options,
        });
        filters_dropdown_widget.setup();
        update_collapsed_note_visibility();
    });
}

export function search_and_update(): void {
    const new_keyword = $<HTMLInputElement>("input#inbox-search").val() ?? "";
    if (new_keyword === search_keyword) {
        return;
    }
    search_keyword = new_keyword;
    current_focus_id = INBOX_SEARCH_ID;
    update_triggered_by_user = true;
    update();
}

function row_in_search_results(keyword: string, text: string): boolean {
    if (keyword === "") {
        return true;
    }
    const search_words = keyword.toLowerCase().split(/\s+/);
    return search_words.every((word) => text.includes(word));
}

function filter_should_hide_dm_row({dm_key}: {dm_key: string}): boolean {
    const recipients_string = people.get_recipients(dm_key);
    const text = recipients_string.join(",").toLowerCase();

    if (!row_in_search_results(search_keyword, text)) {
        return true;
    }

    return false;
}

function filter_should_hide_stream_row({
    stream_id,
    topic,
}: {
    stream_id: number;
    topic: string;
}): boolean {
    const sub = sub_store.get(stream_id);
    if (!sub?.subscribed) {
        return true;
    }

    let current_filter = filters;
    if (inbox_util.is_channel_view()) {
        const channel_id = inbox_util.get_channel_id();
        current_filter = per_channel_filters.get(channel_id) ?? new Set([DEFAULT_FILTER]);
    }

    if (
        current_filter.has(views_util.FILTERS.FOLLOWED_TOPICS) &&
        !user_topics.is_topic_followed(stream_id, topic)
    ) {
        return true;
    }

    if (
        current_filter.has(views_util.FILTERS.UNMUTED_TOPICS) &&
        (user_topics.is_topic_muted(stream_id, topic) ||
            (!inbox_util.is_channel_view() && stream_data.is_muted(stream_id))) &&
        !user_topics.is_topic_unmuted_or_followed(stream_id, topic)
    ) {
        return true;
    }

    const topic_display_name = util.get_final_topic_display_name(topic);
    const text = (sub.name + " " + topic_display_name).toLowerCase();

    if (!row_in_search_results(search_keyword, text)) {
        return true;
    }

    return false;
}

export function collapse_or_expand(container_id: string): void {
    const animation_duration = 200; // ms
    const $toggle_container = $(`#${container_id}`);
    let $all_elements = $(".inbox-header.inbox-folder, .inbox-folder-components");
    const $blocker = $("#inbox-animation-extra-content-blocker");
    $all_elements = $all_elements.add($blocker);
    // If a folder was expanded/collapsed.
    if ($toggle_container.hasClass("inbox-folder")) {
        const $content = $toggle_container.next(".inbox-folder-components");
        animate.collapse_or_expand({
            toggle_class: "inbox-collapsed-state",
            $toggle_container,
            $content,
            $all_elements,
            duration: animation_duration,
        });
        // If a channel was expanded/collapsed.
    } else {
        const $content = $toggle_container.next(".inbox-topic-container");
        // Remove parent`.inbox-folder-components` and
        // add it's contents to `$all_elements`.
        const $parent_folder_components = $toggle_container.closest(".inbox-folder-components");
        $all_elements = $all_elements.not($parent_folder_components);
        const $parent_folder_components_children = $parent_folder_components.children().children();
        $all_elements = $all_elements.add($parent_folder_components_children);
        animate.collapse_or_expand({
            toggle_class: "inbox-collapsed-state",
            $toggle_container,
            $content,
            $all_elements,
            duration: animation_duration,
        });
    }

    if (collapsed_containers.has(container_id)) {
        collapsed_containers.delete(container_id);
        update_collapsed_note_visibility();
    } else {
        collapsed_containers.add(container_id);
        // Show after the animation is complete.
        setTimeout(update_collapsed_note_visibility, animation_duration);
    }

    save_data_to_ls();
}

// We show the note "All of your unread conversations are hidden.
// Click on a section, folder, or channel to see what's inside" for
// the following situations:
//   - All folders collapsed.
//   - If all folders are not collapsed, all visible channels are collapsed.
// For all other cases, the note is hidden.
function should_show_all_folders_collapsed_note(): boolean {
    // TODO: Ideally this would read from internal structures, not the DOM.
    const has_visible_dm_folder = !$("#inbox-dm-header").hasClass("hidden_by_filters");
    if (has_visible_dm_folder && !collapsed_containers.has("inbox-dm-header")) {
        // Some DM content is visible.
        return false;
    }
    // Defined just for code reading clarity.
    const has_visible_but_collapsed_dm_folder = has_visible_dm_folder;

    const visible_folders = [...channel_folders_dict.values()].filter(
        (folder) => folder.is_header_visible,
    );
    if (visible_folders.length === 0) {
        // Nothing at all is visible; unless there is a visible but collapsed
        // DM folder, we show the empty inbox message.
        return has_visible_but_collapsed_dm_folder;
    }

    // At least one uncollapsed row is visible in some folder.
    const has_expanded_content = visible_folders.some((folder) => {
        if (!collapsed_containers.has(folder.header_id)) {
            const folder_streams = [...streams_dict.values()].filter(
                (stream) => stream.folder_id === folder.id && !stream.is_hidden,
            );
            return folder_streams.some(
                (stream) => !collapsed_containers.has(STREAM_HEADER_PREFIX + stream.stream_id),
            );
        }
        return false;
    });
    return !has_expanded_content;
}

function update_collapsed_note_visibility(): void {
    if (should_show_all_folders_collapsed_note()) {
        $("#inbox-collapsed-note").show();
    } else {
        $("#inbox-collapsed-note").hide();
    }
}

function expand_all_folders_and_channels(): void {
    $(
        "#inbox-list .inbox-folder.inbox-collapsed-state:not(.hidden_by_filters), .inbox-streams-container .inbox-header.inbox-collapsed-state:not(.hidden_by_filters)",
    ).each(function () {
        const container_id = $(this).attr("id");
        if (container_id) {
            $(this).removeClass("inbox-collapsed-state");
            collapsed_containers.delete(container_id);
        }
    });

    save_data_to_ls();
    update_collapsed_note_visibility();
}

function focus_current_id(): void {
    assert(current_focus_id !== undefined);
    $(`#${CSS.escape(current_focus_id)}`).trigger("focus");
}

function focus_inbox_search(): void {
    current_focus_id = INBOX_SEARCH_ID;
    focus_current_id();
}

function is_list_focused(): boolean {
    return (
        current_focus_id === undefined ||
        ![INBOX_SEARCH_ID, INBOX_FILTERS_DROPDOWN_ID].includes(current_focus_id)
    );
}

function get_all_rows(no_headers = false): JQuery {
    // Get all rows in the inbox list that are not hidden by filters.
    if (inbox_util.is_channel_view()) {
        return $(".inbox-row").not(".hidden_by_filters");
    }

    // This includes channel folder headers, DM / channel headers and rows.
    const visible_inbox_folder_components =
        "#inbox-list .inbox-folder:not(.inbox-collapsed-state) + .inbox-folder-components";
    let selector =
        // Inbox folder components which display row without any header, i.e. DM row
        `${visible_inbox_folder_components} > .inbox-row, ` +
        // Inbox rows whose folder and header is not collapsed.
        `${visible_inbox_folder_components} .inbox-header:not(.inbox-collapsed-state) + .inbox-topic-container > .inbox-row`;

    if (!no_headers) {
        selector +=
            // Inbox folder headers
            ", #inbox-list .inbox-folder, " +
            // Inbox folder components which display header row, i.e. channel row
            `${visible_inbox_folder_components} .inbox-header`;
    }
    return $(selector).not(".hidden_by_filters");
}

function get_row_index($elt: JQuery): number {
    const $all_rows = get_all_rows();
    const $row = $elt.closest(".inbox-row, .inbox-header");
    return $all_rows.index($row);
}

function focus_clicked_list_element($elt: JQuery): void {
    row_focus = get_row_index($elt);
    update_triggered_by_user = true;
    current_focus_id = $elt.closest(".inbox-row, .inbox-header").attr("id");
}

export function revive_current_focus(): void {
    if (!is_in_focus()) {
        return;
    }
    if (is_list_focused()) {
        set_list_focus();
    } else {
        focus_current_id();
    }
}

function update_closed_compose_text($row: JQuery, is_header_row: boolean): void {
    if (is_header_row) {
        compose_closed_ui.set_standard_text_for_reply_button();
        return;
    }

    let reply_recipient_information: compose_closed_ui.ReplyRecipientInformation;
    const is_dm = $row.parent("#inbox-direct-messages-container").length > 0;
    if (is_dm) {
        const $recipients_info = $row.find(".recipients_info");
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
        const $stream = $row.parent(".inbox-topic-container").prev(".inbox-header");
        reply_recipient_information = {
            stream_id: Number($stream.attr("data-stream-id")),
            topic: $row.find(".inbox-topic-name a").text(),
        };
    }
    compose_closed_ui.update_recipient_text_for_reply_button(reply_recipient_information);
}

export function get_focused_row_message(): {message?: Message | undefined} & (
    | {msg_type: "private"; private_message_recipient?: string}
    | {msg_type: "stream"; stream_id: number; topic?: string}
    | {msg_type?: never}
) {
    if (!is_list_focused()) {
        return {message: undefined};
    }

    const $all_rows = get_all_rows();
    const focused_row = $all_rows.get(row_focus);
    if (!focused_row) {
        // Likely `row_focus` or `current_focus_id` wasn't updated correctly.
        // TODO: Debug this further.
        return {message: undefined};
    }
    const $focused_row = $(focused_row);
    if (is_row_a_header($focused_row)) {
        const is_dm_header = $focused_row.attr("id") === "inbox-dm-header";
        if (is_dm_header) {
            return {message: undefined, msg_type: "private"};
        }

        if ($focused_row.hasClass("inbox-folder")) {
            // This is a channel folder header.
            return {};
        }
        const stream_id = Number($focused_row.attr("data-stream-id"));
        compose_state.set_compose_recipient_id(stream_id);
        return {message: undefined, msg_type: "stream", stream_id};
    }

    const is_dm = $focused_row.parent("#inbox-direct-messages-container").length > 0;
    const conversation_key = $focused_row.attr("id")!.slice(CONVERSATION_ID_PREFIX.length);

    if (is_dm) {
        const row_info = dms_dict.get(conversation_key);
        assert(row_info !== undefined);
        const message = message_store.get(row_info.latest_msg_id);
        if (message === undefined) {
            const recipients = people.user_ids_string_to_emails_string(row_info.user_ids_string);
            assert(recipients !== undefined);
            return {
                msg_type: "private",
                private_message_recipient: recipients,
            };
        }
        return {message};
    }

    // Last case: focused on a topic row.
    // Since inbox is populated based on unread data which is part
    // of /register request, it is possible that we don't have the
    // actual message in our message_store. In that case, we return
    // a fake message object.
    const $topic_menu_elt = $focused_row.find(".inbox-topic-menu");
    const topic = $topic_menu_elt.attr("data-topic-name");
    assert(topic !== undefined);
    const stream_id = Number($topic_menu_elt.attr("data-stream-id"));
    assert(stream_id !== undefined);

    return {
        msg_type: "stream",
        stream_id,
        topic,
    };
}

export function toggle_topic_visibility_policy(): boolean {
    // Since this function is only called from `hotkey`, we don't
    // need to move the focus as it is already on the correct row.

    const inbox_message = get_focused_row_message();
    if (inbox_message.msg_type === "stream" && inbox_message.topic !== undefined) {
        user_topics_ui.toggle_topic_visibility_policy({
            stream_id: inbox_message.stream_id,
            topic: inbox_message.topic,
            type: "stream",
        });
        return true;
    }
    return false;
}

function is_row_a_header($row: JQuery): boolean {
    return $row.hasClass("inbox-header");
}

function set_list_focus(input_key?: string): void {
    // This function is used for both revive_current_focus and
    // setting focus after we modify col_focus and row_focus as per
    // hotkey pressed by user.

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

    const row_to_focus = $all_rows.get(row_focus);
    assert(row_to_focus !== undefined);
    const $row_to_focus = $(row_to_focus);

    current_focus_id = $row_to_focus.attr("id");
    const is_header_row = is_row_a_header($row_to_focus);
    update_closed_compose_text($row_to_focus, is_header_row);
    if (col_focus > COLUMNS.ACTION_MENU) {
        col_focus = COLUMNS.FULL_ROW;
        $row_to_focus.trigger("focus");
        return;
    }

    const cols_to_focus = [row_to_focus, ...$row_to_focus.find("[tabindex=0]")];
    // We assumes that the last column has the highest index is the rightmost column.
    const last_col_index = Number($(cols_to_focus.at(-1)!).attr("data-col-index")!);

    if (col_focus < 0) {
        col_focus = last_col_index;
        $(cols_to_focus.at(-1)!).trigger("focus");
        return;
    }

    // This assumes that the last column has the highest index.
    if (col_focus > last_col_index) {
        col_focus = 0;
        $(cols_to_focus[0]!).trigger("focus");
        return;
    }

    // Find the closest column to focus based on the input key.
    let equal = (a: number, b: number): boolean => b >= a;
    if (input_key && LEFT_NAVIGATION_KEYS.includes(input_key)) {
        equal = (a: number, b: number): boolean => a >= b;
        cols_to_focus.reverse();
    }

    for (const col of cols_to_focus) {
        const col_index = Number($(col).attr("data-col-index"));
        if (equal(col_focus, col_index)) {
            col_focus = col_index;
            $(col).trigger("focus");
            return;
        }
    }
}

function focus_filters_dropdown(): void {
    current_focus_id = INBOX_FILTERS_DROPDOWN_ID;
    $(`#${CSS.escape(INBOX_FILTERS_DROPDOWN_ID)}`).trigger("focus");
}

function is_search_focused(): boolean {
    return current_focus_id === INBOX_SEARCH_ID;
}

function is_filters_dropdown_focused(): boolean {
    return current_focus_id === INBOX_FILTERS_DROPDOWN_ID;
}

function get_page_up_down_delta(): number {
    const element_above = document.querySelector("#inbox-filters");
    const element_down = document.querySelector("#compose");
    assert(element_above !== null && element_down !== null);
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

function page_up_navigation(): void {
    const delta = get_page_up_down_delta();
    const scroll_element = document.documentElement;
    const new_scrollTop = scroll_element.scrollTop - delta;
    if (new_scrollTop <= 0) {
        row_focus = 0;
    }
    scroll_element.scrollTop = new_scrollTop;
    set_list_focus();
}

function page_down_navigation(): void {
    const delta = get_page_up_down_delta();
    const scroll_element = document.documentElement;
    const new_scrollTop = scroll_element.scrollTop + delta;
    const $all_rows = get_all_rows();
    const $last_row = $all_rows.last();
    const last_row_bottom = ($last_row.offset()?.top ?? 0) + ($last_row.outerHeight() ?? 0);
    // Move focus to last row if it is visible and we are at the bottom.
    if (last_row_bottom <= new_scrollTop) {
        row_focus = get_all_rows().length - 1;
    }
    scroll_element.scrollTop = new_scrollTop;
    set_list_focus();
}

export function change_focused_element(input_key: string): boolean {
    const is_first_user_keypress = $("#inbox-view").hasClass("no-visible-focus-outlines");
    if (is_first_user_keypress) {
        // Start showing visible focus outlines.
        $("#inbox-view").removeClass("no-visible-focus-outlines");
    }
    if (is_first_user_keypress && !is_search_focused()) {
        // User has barely scrolled the page.
        if (window.scrollY < 30) {
            // Find the first visible row and focus it.
            const no_headers = true;
            const $first_row = get_all_rows(no_headers).first();
            if ($first_row.length === 0) {
                return true;
            }
            row_focus = get_row_index($first_row);
            current_focus_id = $first_row.attr("id");
            $first_row.trigger("focus");
        }

        // Skip keyboard navigation if this is the first user keypress.
        return true;
    }

    if (input_key === "tab" || input_key === "shift_tab") {
        // Tabbing should be handled by browser but to keep the focus element same
        // when we rerender or user uses other hotkeys, we need to track
        // the current focused element.
        setTimeout(() => {
            const post_tab_focus_elem = document.activeElement;
            if (!(post_tab_focus_elem instanceof HTMLElement)) {
                return;
            }

            if (
                post_tab_focus_elem.id === INBOX_SEARCH_ID ||
                post_tab_focus_elem.id === INBOX_FILTERS_DROPDOWN_ID
            ) {
                current_focus_id = post_tab_focus_elem.id;
            }

            const row_to_focus = post_tab_focus_elem.closest(".inbox-row, .inbox-header");
            if (row_to_focus instanceof HTMLElement) {
                const col_index = $(post_tab_focus_elem)
                    .closest("[tabindex=0]")
                    .attr("data-col-index");
                if (!col_index) {
                    return;
                }

                current_focus_id = row_to_focus.id;
                row_focus = get_row_index($(row_to_focus));
                col_focus = Number.parseInt(col_index, 10);
            }
        }, 0);
        return false;
    }

    if (is_search_focused()) {
        const textInput = $<HTMLInputElement>(`input#${CSS.escape(INBOX_SEARCH_ID)}`).get(0);
        assert(textInput !== undefined);
        const start = textInput.selectionStart ?? 0;
        const end = textInput.selectionEnd ?? 0;
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
                focus_inbox_search();
                return true;
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
                col_focus += 1;
                set_list_focus(input_key);
                return true;
            case LEFT_NAVIGATION_KEYS[0]:
            case LEFT_NAVIGATION_KEYS[1]:
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

function bulk_insert_channel_folders(channel_folders: Set<number>): void {
    sort_channel_folders();
    // Insert missing channel folders.
    let index = 0;
    let previous_folder_id;
    for (const [folder_id, folder_context] of channel_folders_dict) {
        if (channel_folders.has(folder_id)) {
            const $folder_row_html = render_inbox_folder_with_channels({
                ...folder_context,
                topics_dict,
                streams_dict,
            });
            if (index === 0) {
                const $dm_container = $("#inbox-direct-messages-container");
                $dm_container.after($folder_row_html);
            } else {
                assert(previous_folder_id !== undefined);
                const $previous_folder = $(
                    `#${CSS.escape(get_channel_folder_header_id(previous_folder_id))} + .inbox-folder-components`,
                );
                $previous_folder.after($folder_row_html);
            }
        }
        previous_folder_id = folder_id;
        index += 1;
    }
}

export function update(): void {
    // Since inbox shows a vast amount of sorted data,
    // doing surgical updates for everything is hard.
    // So, we focus on updating commonly changed data
    // like unread counts, mentions, collapse state, etc.
    // For rare changes like stream rename, channel folder
    // rename and channel folder updates, we expect the event
    // path to do a complete rerender of the inbox view.
    if (!inbox_util.is_visible()) {
        return;
    }

    if (inbox_util.is_channel_view()) {
        channel_view_topic_widget?.build();
        return;
    }

    const unread_dms = unread.get_unread_pm();
    const unread_dms_count = unread_dms.total_count;
    const unread_dms_dict = unread_dms.pm_dict;
    const has_unread_mention = unread.num_unread_mentions_in_dms() > 0;

    const unread_stream_message = unread.get_unread_topics();
    const unread_streams_dict = unread_stream_message.topic_counts;

    let has_dms_post_filter = false;
    const dm_keys_to_insert: string[] = [];
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
        $inbox_dm_header.find(".unread_mention_info").toggleClass("hidden", !has_unread_mention);
    }

    const folders_info = new Map<number, {unread_count: number; has_unread_mention: boolean}>();
    const channel_folders_to_insert = new Set<number>();

    let has_topics_post_filter = false;
    for (const [stream_id, topic_dict] of unread_streams_dict) {
        const stream_unread = unread.unread_count_info_for_stream(stream_id);
        const stream_unread_count = stream_unread.unmuted_count + stream_unread.muted_count;
        const stream_key = get_stream_key(stream_id);
        let stream_post_filter_unread_count = 0;
        if (stream_unread_count > 0) {
            const stream_topics_data = topics_dict.get(stream_key);

            // Stream isn't rendered.
            if (stream_topics_data === undefined) {
                update_stream_data(stream_id, stream_key, topic_dict);
                const channel_data = streams_dict.get(stream_key);
                assert(channel_data !== undefined);
                // If the folder is also not rendered, it will be once we render
                // the folder, so we skip adding it.
                if (channel_folders_dict.get(channel_data.folder_id)) {
                    insert_stream(stream_key);
                }
                if (!channel_data.is_hidden) {
                    has_topics_post_filter = true;
                }
                const folder_id = channel_data.folder_id;
                const folder_unread_count = folders_info.get(folder_id)?.unread_count ?? 0;
                const folder_has_unread_mention =
                    folders_info.get(folder_id)?.has_unread_mention ?? false;
                folders_info.set(folder_id, {
                    unread_count: folder_unread_count + channel_data.unread_count!,
                    has_unread_mention: folder_has_unread_mention || channel_data.mention_in_unread,
                });
                continue;
            }

            const topic_keys_to_insert: string[] = [];
            const new_stream_data = format_stream(stream_id);
            const stream_archived = new_stream_data.is_archived;
            for (const [topic, {topic_count, latest_msg_id}] of topic_dict) {
                const topic_key = get_topic_key(stream_id, topic);
                if (topic_count) {
                    const old_topic_data = stream_topics_data.get(topic_key);
                    const new_topic_data = format_topic(
                        stream_id,
                        stream_archived,
                        topic,
                        topic_count,
                        latest_msg_id,
                    );
                    stream_topics_data.set(topic_key, new_topic_data);
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
                    stream_topics_data.delete(topic_key);
                    get_row_from_conversation_key(topic_key).remove();
                }
            }
            const old_stream_data = streams_dict.get(stream_key);
            assert(old_stream_data !== undefined);
            new_stream_data.is_hidden = stream_post_filter_unread_count === 0;
            new_stream_data.unread_count = stream_post_filter_unread_count;
            const folder_id = new_stream_data.folder_id;
            const folder_unread_count = folders_info.get(folder_id)?.unread_count ?? 0;
            const folder_has_unread_mention =
                folders_info.get(folder_id)?.has_unread_mention ?? false;
            folders_info.set(folder_id, {
                unread_count: folder_unread_count + stream_post_filter_unread_count,
                has_unread_mention: folder_has_unread_mention || new_stream_data.mention_in_unread,
            });
            streams_dict.set(stream_key, new_stream_data);
            rerender_stream_inbox_header_if_needed(new_stream_data, old_stream_data);
            topics_dict.set(stream_key, get_sorted_row_dict(stream_topics_data));
            insert_topics(topic_keys_to_insert, stream_key);
        } else {
            topics_dict.delete(stream_key);
            streams_dict.delete(stream_key);
            get_stream_container(stream_key).remove();
        }
    }

    for (const [folder_id, folder_info] of folders_info.entries()) {
        const folder_dict = channel_folders_dict.get(folder_id);
        const name = get_folder_name_from_id(folder_id);
        const is_collapsed = collapsed_containers.has(get_channel_folder_header_id(folder_id));
        const header_id = get_channel_folder_header_id(folder_id);
        const is_header_visible = folder_info.unread_count > 0;
        const order = get_folder_order_from_id(folder_id);
        channel_folders_dict.set(folder_id, {
            header_id,
            is_header_visible,
            id: folder_id,
            unread_count: folder_info.unread_count,
            has_unread_mention: folder_info.has_unread_mention,
            name,
            is_collapsed,
            order,
        });

        if (folder_dict === undefined) {
            channel_folders_to_insert.add(folder_id);
        } else {
            rerender_channel_folder_header_if_needed(
                folder_dict,
                channel_folders_dict.get(folder_id)!,
            );
        }
    }

    // Remove channel folders that are not in the updated folders_info.
    const folder_ids_to_keep = new Set(folders_info.keys());
    for (const [folder_id] of channel_folders_dict) {
        if (!folder_ids_to_keep.has(folder_id)) {
            channel_folders_dict.delete(folder_id);
            const $rendered_folder_row = $(
                `#${CSS.escape(get_channel_folder_header_id(folder_id))}`,
            );
            $rendered_folder_row.next(".inbox-folder-components").remove();
            $rendered_folder_row.remove();
        }
    }

    bulk_insert_channel_folders(channel_folders_to_insert);

    update_name_of_other_channels_folder({
        should_update_ui: true,
    });

    const has_visible_unreads = has_dms_post_filter || has_topics_post_filter;
    show_empty_inbox_text(has_visible_unreads);

    // We want to avoid weird jumps when user is interacting with Inbox
    // and we are updating the view. So, we only reset current focus if
    // the update was triggered by user. This can mean `row_focus` can
    // be out of bounds, so we need to fix that.
    if (update_triggered_by_user) {
        setTimeout(revive_current_focus, 0);
        update_triggered_by_user = false;
    } else {
        if (row_focus >= get_all_rows().length) {
            revive_current_focus();
        }
    }
    update_collapsed_note_visibility();
}

function get_focus_class_for_header(): string {
    let focus_class = ".collapsible-button";

    switch (col_focus) {
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

function get_focus_class_for_row(): string {
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

function is_element_visible(element_position: DOMRect): boolean {
    const element_above = document.querySelector("#inbox-filters");
    const element_down = document.querySelector("#compose");
    assert(element_above !== null && element_down !== null);
    const visible_top = element_above.getBoundingClientRect().bottom;
    const visible_bottom = element_down.getBoundingClientRect().top;

    if (element_position.top >= visible_top && element_position.bottom <= visible_bottom) {
        return true;
    }
    return false;
}

function center_focus_if_offscreen(): void {
    // Move focused to row to visible area so to avoid
    // it being under compose box or inbox filters.
    const $elt = $(".inbox-row:focus, .inbox-header:focus");
    if ($elt[0] === undefined) {
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

function move_focus_to_visible_area(): void {
    if (is_waiting_for_revive_current_focus) {
        return;
    }

    // Focus on the row below inbox filters if the focused
    // row is not visible.
    if (!inbox_util.is_visible() || !is_list_focused()) {
        return;
    }

    const $all_rows = get_all_rows();
    if ($all_rows.length <= 3) {
        // No need to process anything if there are only a few rows.
        return;
    }

    let row = $all_rows[row_focus];
    if (row === undefined) {
        row_focus = $all_rows.length - 1;
        row = $all_rows[row_focus];
        assert(row !== undefined);
        revive_current_focus();
    }

    const elt_pos = row.getBoundingClientRect();
    if (is_element_visible(elt_pos)) {
        return;
    }

    const inbox_filters_props = util.the($("#inbox-filters")).getBoundingClientRect();
    const compose_top = window.innerHeight - $("#compose").outerHeight(true)!;
    const inbox_center_x = (inbox_filters_props.left + inbox_filters_props.right) / 2;
    const inbox_center_y = (compose_top + inbox_filters_props.bottom) / 2;
    const element_in_row = document.elementFromPoint(inbox_center_x, inbox_center_y);
    if (!element_in_row) {
        // The table is too short for there to be an topic row element
        // at the center of the table region; in that case, we just
        // select the last element.
        row_focus = $all_rows.length - 1;
    } else {
        const $element_in_row = $(element_in_row);

        let $inbox_row = $element_in_row.closest(".inbox-row");
        if ($inbox_row.length === 0) {
            $inbox_row = $element_in_row.closest(".inbox-header");
        }

        row_focus = $all_rows.index($inbox_row.get(0));
    }
    revive_current_focus();
}

export function is_in_focus(): boolean {
    return inbox_util.is_visible() && views_util.is_in_focus();
}

export function initialize({hide_other_views}: {hide_other_views: () => void}): void {
    hide_other_views_callback = hide_other_views;
    $(document).on(
        "scroll",
        _.throttle(() => {
            if (!inbox_util.is_visible()) {
                // This check is duplicated with move_focus_to_visible_area. It
                // is worth doing to avoid the performance hit of wrapping
                // requestAnimationFramearound a likely noop.
                return;
            }
            requestAnimationFrame(move_focus_to_visible_area);
        }, 100),
    );

    $("body").on(
        "input",
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

    $("body").on(
        "click",
        "#inbox-list .inbox-header .collapsible-button",
        function (this: HTMLElement, e) {
            const $elt = $(this);
            const container_id = $elt.parents(".inbox-header").attr("id");
            assert(container_id !== undefined);
            col_focus = COLUMNS.FULL_ROW;
            focus_clicked_list_element($elt);
            collapse_or_expand(container_id);
            e.stopPropagation();
        },
    );

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

    $("body").on("click", "#inbox-collapsed-note #inbox-expand-all-button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        expand_all_folders_and_channels();
    });

    $("body").on("click", "#inbox-list .inbox-left-part-wrapper", function (this: HTMLElement, e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        let $elt = $(this);
        const href = $elt.find("a").attr("href");
        col_focus = COLUMNS.FULL_ROW;
        if (href !== undefined) {
            window.location.href = href;
        } else {
            $elt = $elt.closest(".inbox-header");
            collapse_or_expand($elt.attr("id")!);
        }
        focus_clicked_list_element($elt);
    });

    $("body").on("click", "#inbox-list .on_hover_dm_read", function (this: HTMLElement, e) {
        e.stopPropagation();
        e.preventDefault();
        const $elt = $(this);
        col_focus = COLUMNS.UNREAD_COUNT;
        focus_clicked_list_element($elt);
        const user_ids_string = $elt.attr("data-user-ids-string");
        if (user_ids_string) {
            // direct message row
            unread_ops.mark_pm_as_read(user_ids_string);
        }
    });

    $("body").on("click", "#inbox-list .on_hover_topic_read", function (this: HTMLElement, e) {
        e.stopPropagation();
        e.preventDefault();
        const $elt = $(this);
        col_focus = COLUMNS.UNREAD_COUNT;
        focus_clicked_list_element($elt);
        const user_ids_string = $elt.attr("data-user-ids-string");
        if (user_ids_string) {
            // direct message row
            unread_ops.mark_pm_as_read(user_ids_string);
            return;
        }
        const stream_id = Number($elt.attr("data-stream-id"));
        const topic = $elt.attr("data-topic-name");
        if (topic !== undefined) {
            unread_ops.mark_topic_as_read(stream_id, topic);
        } else {
            unread_ops.mark_stream_as_read(stream_id);
        }
    });

    $("body").on("click", "#inbox-list .change_visibility_policy", function (this: HTMLElement) {
        const $elt = $(this);
        col_focus = COLUMNS.TOPIC_VISIBILITY;
        focus_clicked_list_element($elt);
    });

    $("body").on("click", "#inbox-search", () => {
        current_focus_id = INBOX_SEARCH_ID;
        compose_closed_ui.set_standard_text_for_reply_button();
    });

    $("body").on(
        "click",
        "#inbox-list .toggle-channel-visibility",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            const $elt = $(this);
            focus_clicked_list_element($elt);
            const stream_id = Number($elt.attr("data-stream-id"));
            if (stream_id) {
                const sub = sub_store.get(stream_id);
                if (sub) {
                    stream_settings_api.set_stream_property(sub, {
                        property: "is_muted",
                        value: false,
                    });
                }
            }
        },
    );

    $("body").on("keydown", "#inbox-list .toggle-channel-visibility", (e) => {
        if (e.metaKey || e.ctrlKey) {
            return;
        }

        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
            e.stopPropagation();

            const $elt = $(e.currentTarget);
            $elt.trigger("click");
        }
    });

    $(document).on("compose_canceled.zulip", () => {
        if (inbox_util.is_visible()) {
            revive_current_focus();
        }
    });
}
