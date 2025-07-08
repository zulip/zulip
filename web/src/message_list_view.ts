import autosize from "autosize";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as internal_url from "../shared/src/internal_url.ts";
import * as resolved_topic from "../shared/src/resolved_topic.ts";
import render_bookend from "../templates/bookend.hbs";
import render_login_to_view_image_button from "../templates/login_to_view_image_button.hbs";
import render_message_group from "../templates/message_group.hbs";
import render_message_list from "../templates/message_list.hbs";
import render_recipient_row from "../templates/recipient_row.hbs";
import render_single_message from "../templates/single_message.hbs";

import * as activity from "./activity.ts";
import * as blueslip from "./blueslip.ts";
import * as compose_fade from "./compose_fade.ts";
import * as condense from "./condense.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_edit from "./message_edit.ts";
import type {MessageList} from "./message_list.ts";
import * as message_list_tooltips from "./message_list_tooltips.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as message_viewport from "./message_viewport.ts";
import type {MessageViewportInfo} from "./message_viewport.ts";
import * as muted_users from "./muted_users.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as popovers from "./popovers.ts";
import * as reactions from "./reactions.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as rows from "./rows.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as submessage from "./submessage.ts";
import {is_same_day} from "./time_zone_util.ts";
import * as timerender from "./timerender.ts";
import type {TopicLink} from "./types.ts";
import * as typing_data from "./typing_data.ts";
import * as typing_events from "./typing_events.ts";
import * as user_topics from "./user_topics.ts";
import type {AllVisibilityPolicies} from "./user_topics.ts";
import * as util from "./util.ts";

export type MessageContainer = {
    background_color?: string;
    date_divider_html: string | undefined;
    year_changed: boolean;
    include_recipient: boolean;
    include_sender: boolean;
    is_hidden: boolean;
    last_edit_timestamp: number | undefined;
    last_moved_timestamp: number | undefined;
    mention_classname: string | undefined;
    message_edit_notices_in_left_col: boolean;
    message_edit_notices_alongside_sender: boolean;
    message_edit_notices_for_status_message: boolean;
    modified: boolean;
    edited: boolean;
    moved: boolean;
    msg: Message;
    sender_is_bot: boolean;
    sender_is_guest: boolean;
    sender_is_deactivated: boolean;
    should_add_guest_indicator_for_sender: boolean;
    small_avatar_url: string;
    status_message: string | false;
    stream_url?: string;
    subscribed?: boolean;
    pm_with_url?: string;
    timestr: string;
    topic_url?: string;
    unsubscribed?: boolean;
    want_date_divider: boolean;
};

export type MessageGroup = {
    bookend_top?: boolean;
    date: string;
    date_unchanged: boolean;
    message_containers: MessageContainer[];
    message_group_id: string;
} & (
    | {
          is_stream: true;
          all_visibility_policies: AllVisibilityPolicies;
          display_recipient: string;
          invite_only: boolean;
          is_subscribed: boolean;
          is_topic_editable: boolean;
          is_web_public: boolean;
          just_unsubscribed?: boolean;
          match_topic: string | undefined;
          recipient_bar_color: string;
          stream_id: number;
          stream_name?: string;
          stream_privacy_icon_color: string;
          stream_url: string;
          is_archived: boolean;
          subscribed?: boolean;
          topic: string;
          topic_display_name: string;
          is_empty_string_topic: boolean;
          topic_is_resolved: boolean;
          topic_links: TopicLink[] | undefined;
          topic_url: string | undefined;
          user_can_resolve_topic: boolean;
          visibility_policy: number | false;
          always_display_date: boolean;
      }
    | {
          is_stream: false;
          display_recipient: {email: string; full_name: string; id: number}[];
          display_reply_to_for_tooltip: string;
          is_private: true;
          pm_with_url: string;
          recipient_users: RecipientRowUser[];
          always_display_date: boolean;
          is_dm_with_self: boolean;
      }
);

type RenderingPlan = {
    append_groups: MessageGroup[];
    prepend_groups: MessageGroup[];
    rerender_groups: MessageGroup[];
    append_messages: MessageContainer[];
};

function same_day(earlier_msg: Message | undefined, later_msg: Message | undefined): boolean {
    if (earlier_msg === undefined || later_msg === undefined) {
        return false;
    }
    return is_same_day(
        earlier_msg.timestamp * 1000,
        later_msg.timestamp * 1000,
        timerender.display_time_zone,
    );
}

function same_year(earlier_msg: Message | undefined, later_msg: Message | undefined): boolean {
    if (earlier_msg === undefined || later_msg === undefined) {
        return true;
    }
    return (
        new Date(earlier_msg.timestamp * 1000).getFullYear() ===
        new Date(later_msg.timestamp * 1000).getFullYear()
    );
}

function same_sender(a: MessageContainer | undefined, b: MessageContainer | undefined): boolean {
    if (a === undefined || b === undefined) {
        return false;
    }
    return a.msg.sender_id === b.msg.sender_id;
}

function same_recipient(a: MessageContainer | undefined, b: MessageContainer | undefined): boolean {
    if (a === undefined || b === undefined) {
        return false;
    }
    return util.same_recipient(a.msg, b.msg);
}

function get_group_display_date(message: Message, display_year: boolean): string {
    const time = new Date(message.timestamp * 1000);
    const date_element = timerender.render_date(time, display_year);

    return date_element.outerHTML;
}

function update_group_date(group: MessageGroup, message: Message, prev: Message | undefined): void {
    // Mark whether we should display a date marker because this
    // message has a different date than the previous one.
    group.date_unchanged = same_day(message, prev);
}

function clear_group_date(group: MessageGroup): void {
    group.date_unchanged = false;
}

function clear_message_date_divider(message_container: MessageContainer): void {
    // see update_message_date_divider for how
    // these get set
    message_container.want_date_divider = false;
    message_container.date_divider_html = undefined;
}

function update_message_date_divider(opts: {
    prev_msg_container: MessageContainer | undefined;
    curr_msg_container: MessageContainer;
}): void {
    Object.assign(
        opts.curr_msg_container,
        get_message_date_divider_data({
            prev_message: opts.prev_msg_container?.msg,
            curr_message: opts.curr_msg_container.msg,
            display_year: !same_year(opts.curr_msg_container.msg, opts.prev_msg_container?.msg),
        }),
    );
}

function get_message_date_divider_data(opts: {
    prev_message: Message | undefined;
    curr_message: Message;
    display_year: boolean;
}): {
    want_date_divider: boolean;
    date_divider_html: string | undefined;
} {
    const prev_message = opts.prev_message;
    const curr_message = opts.curr_message;
    const display_year = opts.display_year;

    if (!prev_message || same_day(curr_message, prev_message)) {
        return {
            want_date_divider: false,
            date_divider_html: undefined,
        };
    }
    const curr_time = new Date(curr_message.timestamp * 1000);

    return {
        want_date_divider: true,
        date_divider_html: timerender.render_date(curr_time, display_year).outerHTML,
    };
}

function get_timestr(message: Message): string {
    const time = new Date(message.timestamp * 1000);
    return timerender.stringify_time(time);
}

function get_topic_edit_properties(message: Message): {
    is_topic_editable: boolean;
} {
    const is_topic_editable = message_edit.is_topic_editable(message);

    return {
        is_topic_editable,
    };
}

type RecipientRowUser = {
    full_name: string;
    should_add_guest_user_indicator: boolean;
};
function get_users_for_recipient_row(message: Message): RecipientRowUser[] {
    const user_ids = people.pm_with_user_ids(message);
    assert(user_ids !== undefined);
    const users = user_ids.map((user_id) => {
        let full_name;
        const is_bot = people.is_valid_bot_user(user_id);
        if (muted_users.is_user_muted(user_id)) {
            full_name = $t({defaultMessage: "Muted user"});
        } else {
            full_name = people.get_full_name(user_id);
        }
        return {
            full_name,
            should_add_guest_user_indicator: people.should_add_guest_user_indicator(user_id),
            is_bot,
        };
    });

    function compare_by_name(a: RecipientRowUser, b: RecipientRowUser): number {
        return util.strcmp(a.full_name, b.full_name);
    }

    return users.sort(compare_by_name);
}

let message_id_to_focus_after_processing_message_events:
    | {
          id: number;
          selectionStart: number;
          selectionEnd: number;
      }
    | {
          id: undefined;
          selectionStart: undefined;
          selectionEnd: undefined;
      } = {
    id: undefined,
    selectionStart: undefined,
    selectionEnd: undefined,
};

function reset_restore_message_edit_focus_state(): void {
    message_id_to_focus_after_processing_message_events = {
        id: undefined,
        selectionStart: undefined,
        selectionEnd: undefined,
    };
}

function capture_user_message_editing_state(): void {
    if (document.activeElement?.classList.contains("message_edit_content")) {
        assert(document.activeElement instanceof HTMLTextAreaElement);
        message_id_to_focus_after_processing_message_events = {
            id: rows.get_message_id(document.activeElement),
            selectionStart: document.activeElement.selectionStart,
            selectionEnd: document.activeElement.selectionEnd,
        };
    } else {
        reset_restore_message_edit_focus_state();
    }
}

function maybe_restore_focus_to_message_edit_form(): void {
    if (
        // It is possible that selected message might not be the one
        // user was editing but is less likely the case. It makes
        // things complicated to think about with selected message being different
        // from the message edit form we are trying to restore focus to.
        // So, we simply only restore focus if the selected message is the
        // one user was editing.
        message_lists.current?.data.selected_id() !==
        message_id_to_focus_after_processing_message_events.id
    ) {
        // If user has navigated away from the message they were editing,
        // we don't want to restore focus to the message edit form since
        // we don't want to capture hotkey inside the message edit form
        // when they navigate back to the message they were editing.
        reset_restore_message_edit_focus_state();
    }

    setTimeout(() => {
        const $message_edit_content = message_lists.current
            ?.selected_row()
            .find<HTMLTextAreaElement>(".message_edit_content");
        if (!$message_edit_content || $message_edit_content.length === 0) {
            return;
        }

        $message_edit_content.trigger("focus");
        util.the($message_edit_content).setSelectionRange(
            message_id_to_focus_after_processing_message_events.selectionStart!,
            message_id_to_focus_after_processing_message_events.selectionEnd!,
        );
        reset_restore_message_edit_focus_state();
    }, 0);
}

type SubscriptionMarkers = {
    bookend_top: boolean;
    stream_name: string;
    subscribed?: boolean;
    just_unsubscribed?: boolean;
};
function populate_group_from_message(
    message: Message,
    date_unchanged: boolean,
    year_changed: boolean,
    subscription_markers: SubscriptionMarkers | undefined,
): MessageGroup {
    const is_stream = message.is_stream;
    const is_private = message.is_private;
    const display_recipient = message.display_recipient;
    const message_group_id = _.uniqueId("message_group_");
    const date = get_group_display_date(message, year_changed);

    // Each searched message is a self-contained result,
    // so we always display date in the recipient bar for those messages.
    const always_display_date = narrow_state.is_search_view();
    if (is_stream) {
        assert(message.type === "stream");
        // stream messages have string display_recipient
        assert(typeof display_recipient === "string");
        const color = stream_data.get_color(message.stream_id);
        const recipient_bar_color = stream_color.get_recipient_bar_color(color);
        const stream_privacy_icon_color = stream_color.get_stream_privacy_icon_color(color);
        const invite_only = stream_data.is_invite_only_by_stream_id(message.stream_id);
        const is_web_public = stream_data.is_web_public(message.stream_id);
        const topic = message.topic;
        const topic_display_name = util.get_final_topic_display_name(topic);
        const is_empty_string_topic = topic === "";
        const match_topic = util.get_match_topic(message);
        const stream_url = hash_util.channel_url_by_user_setting(message.stream_id);
        const is_archived = stream_data.is_stream_archived(message.stream_id);
        const topic_url = internal_url.by_stream_topic_url(
            message.stream_id,
            message.topic,
            sub_store.maybe_get_stream_name,
            message.id,
        );

        const sub = sub_store.get(message.stream_id);
        let stream_id;
        if (sub === undefined) {
            // Hack to handle unusual cases like the tutorial where
            // the streams used don't actually exist in the subs
            // module.  Ideally, we'd clean this up by making the
            // tutorial populate stream_settings_ui.ts "properly".
            stream_id = -1;
        } else {
            stream_id = sub.stream_id;
        }

        const is_subscribed = stream_data.is_subscribed(stream_id);
        const topic_is_resolved = resolved_topic.is_resolved(topic);
        const user_can_resolve_topic = stream_data.can_resolve_topics(sub);
        const visibility_policy = user_topics.get_topic_visibility_policy(stream_id, topic);
        // The following field is not specific to this group, but this is the
        // easiest way we've figured out for passing the data to the template rendering.
        const all_visibility_policies = user_topics.all_visibility_policies;

        const topic_links = message.topic_links;

        return {
            message_group_id,
            message_containers: [],
            is_stream,
            ...get_topic_edit_properties(message),
            user_can_resolve_topic,
            ...subscription_markers,
            date,
            display_recipient,
            date_unchanged,
            topic_links,
            topic,
            topic_display_name,
            is_empty_string_topic,
            recipient_bar_color,
            stream_privacy_icon_color,
            invite_only,
            is_web_public,
            match_topic,
            stream_url,
            is_archived,
            topic_url,
            stream_id,
            is_subscribed,
            topic_is_resolved,
            visibility_policy,
            all_visibility_policies,
            always_display_date,
        };
    }
    // Private message group
    assert(is_private);
    assert(typeof display_recipient !== "string");
    const user_ids = people.pm_with_user_ids(message);
    assert(user_ids !== undefined);
    return {
        message_group_id,
        message_containers: [],
        is_stream,
        is_private,
        ...get_topic_edit_properties(message),
        date,
        date_unchanged,
        display_recipient,
        pm_with_url: message.pm_with_url,
        recipient_users: get_users_for_recipient_row(message),
        is_dm_with_self: people.is_direct_message_conversation_with_self(user_ids),
        display_reply_to_for_tooltip: message_store.get_pm_full_names(user_ids),
        always_display_date,
    };
}

// MessageListView is the module responsible for rendering a
// MessageList into the DOM, and maintaining it over time.
//
// Logic to compute context, render templates, insert them into
// the DOM, and generally
export class MessageListView {
    // The MessageList that this MessageListView is responsible for rendering.
    list: MessageList;
    // The jQuery element for the rendered list element.
    $list: JQuery;
    // TODO: Access this via .list.data.
    collapse_messages: boolean;

    // These three data structures keep track of groups of messages in the DOM.
    //
    // The message_groups are blocks of messages rendered into the
    // DOM that will share a common recipient bar heading.
    //
    // A message_container an object containing a Message object
    // plus additional computed metadata needed for rendering it
    // in the DOM.
    //
    // _rows contains jQuery objects for the `message_row`
    // elements rendered by single_message.hbs.
    //
    // TODO: Consider renaming _message_groups to something like _recipient_groups.
    // TODO: Consider renaming _rows to something like $rows.
    _rows: Map<number, JQuery>;
    message_containers: Map<number, MessageContainer>;
    _message_groups: MessageGroup[];

    // For performance reasons, this module renders at most
    // _RENDER_WINDOW_SIZE messages into the DOM at a time, and
    // will transparently adjust which messages are rendered
    // whenever the user scrolls within _RENDER_THRESHOLD of the
    // edge of the rendered window.
    //
    // These two values are a half-open interval keeping track of
    // what range of messages is currently rendered in the dOM.
    _render_win_start: number;
    _render_win_end: number;

    // ID of message under the sticky recipient bar if there is one.
    sticky_recipient_message_id: number | undefined;

    // Number of messages to render at a time
    _RENDER_WINDOW_SIZE = 250;
    // Number of messages away from edge of render window at which we
    // trigger a re-render
    _RENDER_THRESHOLD = 50;

    constructor(list: MessageList, collapse_messages: boolean, is_node_test = false) {
        this.list = list;
        this._add_message_list_to_DOM();
        this.$list = $(`.message-list[data-message-list-id="${this.list.id}"]`);
        this.collapse_messages = collapse_messages;
        this._rows = new Map();
        this.message_containers = new Map();
        this._message_groups = [];
        if (!is_node_test) {
            // Skip running this in node tests.
            this.clear_table();
        }
        this._render_win_start = 0;
        this._render_win_end = 0;
        this.sticky_recipient_message_id = undefined;
    }

    _add_message_list_to_DOM(): void {
        $("#message-lists-container").append(
            $(render_message_list({message_list_id: this.list.id})),
        );
    }

    _get_message_edited_and_moved_vars(message: Message): {
        last_edit_timestamp: number | undefined;
        last_moved_timestamp: number | undefined;
        edited: boolean;
        moved: boolean;
        modified: boolean;
    } {
        let last_edit_timestamp;
        if (message.local_edit_timestamp !== undefined) {
            last_edit_timestamp = message.local_edit_timestamp;
        } else {
            last_edit_timestamp = message.last_edit_timestamp;
        }
        const last_moved_timestamp = message.last_moved_timestamp;

        return {
            last_edit_timestamp,
            last_moved_timestamp,
            edited: last_edit_timestamp !== undefined,
            moved: last_moved_timestamp !== undefined,
            modified: last_edit_timestamp !== undefined || last_moved_timestamp !== undefined,
        };
    }

    is_current_message_list(): boolean {
        return this.list === message_lists.current;
    }

    get_calculated_message_container_variables(
        message: Message,
        existing_include_sender: boolean,
        is_revealed = false,
    ): {
        timestr: string;
        background_color?: string;
        small_avatar_url: string;
        sender_is_bot: boolean;
        sender_is_guest: boolean;
        sender_is_deactivated: boolean;
        should_add_guest_indicator_for_sender: boolean;
        is_hidden: boolean;
        mention_classname: string | undefined;
        include_sender: boolean;
        status_message: string | false;
        last_edit_timestamp: number | undefined;
        last_moved_timestamp: number | undefined;
        edited: boolean;
        moved: boolean;
        modified: boolean;
    } {
        const is_typing = typing_data.is_message_editing(message.id);
        if (is_typing) {
            // Ensure the typing animation is rendered when a user switches
            // to a view where someone is editing a message.
            setTimeout(() => {
                typing_events.render_message_editing_typing(message.id, true);
            }, 0);
        }

        /*
            If the message needs to be hidden because the sender was muted, we do
            a few things:
            1. Hide the sender avatar and name.
            2. Hide reactions on that message.
            3. Do not give a background color to that message even if it mentions the
               current user.

            Further, is a hidden message was just revealed, we make sure to show
            the sender.
        */

        const is_hidden = muted_users.is_user_muted(message.sender_id) && !is_revealed;

        let mention_classname;

        // Make sure the right thing happens if the message was edited to mention us.
        if (!is_hidden && message.mentioned) {
            // Currently the API does not differentiate between a group mention and
            // a user mention. For now, we parse the markdown to see if the message
            // mentions the user.
            let is_user_mention = false;
            const $msg = $(message.content);
            $msg.find(".user-mention:not(.silent)").each(function () {
                const user_id = rendered_markdown.get_user_id_for_mention_button(this);
                if (user_id === "*") {
                    return;
                }
                if (user_id !== undefined && people.is_my_user_id(user_id)) {
                    is_user_mention = true;
                }
            });

            // If a message includes a user mention, then we don't care if there is a
            // group/wildcard mention, and color the message as a user mention. If the
            // message didn't include a user mention, then it was a usergroup/wildcard
            // mention (which is the only other option for `mentioned` being true).
            if (message.mentioned_me_directly && is_user_mention) {
                // Highlight messages having personal mentions only in DMs and subscribed streams.
                if (
                    message.type === "private" ||
                    stream_data.is_user_subscribed(message.stream_id, people.my_current_user_id())
                ) {
                    mention_classname = "direct_mention";
                } else {
                    mention_classname = undefined;
                }
            } else {
                mention_classname = "group_mention";
            }
        } else {
            mention_classname = undefined;
        }
        let include_sender = existing_include_sender && !is_hidden;
        if (is_revealed) {
            // If the message is to be revealed, we show the sender anyways, because the
            // the first message in the group (which would hold the sender) can still be
            // hidden.
            include_sender = true;
        }

        const sender_is_bot = people.sender_is_bot(message);
        const sender_is_guest = people.sender_is_guest(message);
        const sender_is_deactivated = people.sender_is_deactivated(message);
        const should_add_guest_indicator_for_sender = people.should_add_guest_user_indicator(
            message.sender_id,
        );

        const small_avatar_url = people.small_avatar_url(message);
        let background_color;
        if (message.type === "stream") {
            background_color = stream_data.get_color(message.stream_id);
        }

        return {
            timestr: get_timestr(message),
            // this is only relevant for streams, don't use it if it wasn't set
            ...(background_color && {background_color}),
            small_avatar_url,
            sender_is_bot,
            sender_is_guest,
            sender_is_deactivated,
            should_add_guest_indicator_for_sender,
            is_hidden,
            mention_classname,
            include_sender,
            ...this._maybe_get_me_message(is_hidden, message),
            ...this._get_message_edited_and_moved_vars(message),
        };
    }

    maybe_add_subscription_marker_to_group(
        group: MessageGroup,
        last_message: Message | undefined,
        first_message: Message,
    ): void {
        const markers = this.get_possible_group_subscription_markers(last_message, first_message);
        if (markers) {
            Object.assign(group, markers);
        }
    }

    get_possible_group_subscription_markers(
        last_message: Message | undefined,
        first_message: Message,
    ): SubscriptionMarkers | undefined {
        // The `historical` flag is present on messages which were
        // sent a time when the current user was not subscribed to the
        // stream receiving the message.
        //
        // When a narrow contains only messages within a given stream,
        // we can infer that whenever the historical flag flips
        // between adjacent messages, the current user must have
        // (un)subscribed in between those messages.
        if (!this.list.data.filter.has_operator("channel")) {
            return undefined;
        }
        if (last_message === undefined) {
            return undefined;
        }

        const last_subscribed = !last_message.historical;
        const first_subscribed = !first_message.historical;
        assert(first_message.type === "stream");
        const stream_id = first_message.stream_id;
        const stream_name = stream_data.get_stream_name_from_id(stream_id);

        if (!last_subscribed && first_subscribed) {
            return {
                bookend_top: true,
                subscribed: true,
                stream_name,
            };
        }

        if (last_subscribed && !first_subscribed) {
            return {
                bookend_top: true,
                just_unsubscribed: true,
                stream_name,
            };
        }

        return undefined;
    }

    build_message_groups(messages: Message[]): MessageGroup[] {
        const new_message_groups: MessageGroup[] = [];

        let current_group: MessageGroup;
        let current_group_message_containers: MessageContainer[] = [];

        let prev_message_container: MessageContainer | undefined;

        const add_message_container_to_group = (message_container: MessageContainer): void => {
            current_group_message_containers.push(message_container);
        };

        const start_group = (
            prev_message: Message | undefined,
            message_for_next_group: Message,
        ): void => {
            current_group = populate_group_from_message(
                message_for_next_group,
                same_day(message_for_next_group, prev_message),
                !same_year(message_for_next_group, prev_message),
                this.get_possible_group_subscription_markers(prev_message, message_for_next_group),
            );
        };

        const finish_group = (): void => {
            if (current_group_message_containers.length > 0) {
                current_group.message_containers = current_group_message_containers;
                new_message_groups.push(current_group);
            }
            current_group_message_containers = [];
        };

        for (const message of messages) {
            const message_reactions = reactions.get_message_reactions(message);
            message.message_reactions = message_reactions;

            // These will be used to build the message container
            let include_recipient = false;
            let subscribed;
            let unsubscribed;
            let stream_url;
            let topic_url;
            let pm_with_url;
            let include_sender;
            let want_date_divider;
            let date_divider_html;
            const year_changed = !same_year(message, prev_message_container?.msg);

            if (
                prev_message_container &&
                util.same_recipient(prev_message_container.msg, message) &&
                this.collapse_messages &&
                prev_message_container.msg.historical === message.historical
            ) {
                const date_divider_data = get_message_date_divider_data({
                    prev_message: prev_message_container.msg,
                    curr_message: message,
                    display_year: year_changed,
                });
                want_date_divider = date_divider_data.want_date_divider;
                date_divider_html = date_divider_data.date_divider_html;
            } else {
                finish_group();
                start_group(prev_message_container?.msg, message);
                want_date_divider = false;
                date_divider_html = undefined;
                include_recipient = true;
                subscribed = false;
                unsubscribed = false;

                if (message.type === "stream") {
                    stream_url = hash_util.channel_url_by_user_setting(message.stream_id);
                    topic_url = hash_util.by_stream_topic_url(message.stream_id, message.topic);
                } else {
                    pm_with_url = message.pm_with_url;
                }
            }

            include_sender = true;
            if (
                !include_recipient &&
                prev_message_container &&
                !prev_message_container.status_message &&
                same_day(prev_message_container.msg, message) &&
                prev_message_container.msg.sender_id === message.sender_id
            ) {
                include_sender = false;
            }

            const calculated_variables = this.get_calculated_message_container_variables(
                message,
                include_sender,
            );
            const message_container = {
                msg: message,
                include_recipient,
                ...(subscribed && {subscribed}),
                ...(unsubscribed && {unsubscribed}),
                ...(stream_url && {stream_url}),
                ...(topic_url && {topic_url}),
                ...(pm_with_url && {pm_with_url}),
                want_date_divider,
                date_divider_html,
                year_changed,
                ...calculated_variables,
                ...this.get_edited_notice_locations(
                    include_sender,
                    calculated_variables.is_hidden,
                    Boolean(calculated_variables.status_message),
                ),
            };
            add_message_container_to_group(message_container);

            prev_message_container = message_container;
        }

        finish_group();

        return new_message_groups;
    }

    join_message_groups(
        first_group: MessageGroup | undefined,
        second_group: MessageGroup | undefined,
    ): boolean {
        // join_message_groups will combine groups if they have the
        // same_recipient and the view supports collapsing, otherwise
        // it may add a subscription_marker if required.  It returns
        // true if the two groups were joined in to one and the
        // second_group should be ignored.
        if (first_group === undefined || second_group === undefined) {
            return false;
        }
        const last_msg_container = first_group.message_containers.at(-1);
        const first_msg_container = second_group.message_containers[0];
        assert(first_msg_container !== undefined);

        // Join two groups into one.
        if (
            this.collapse_messages &&
            same_recipient(last_msg_container, first_msg_container) &&
            last_msg_container!.msg.historical === first_msg_container.msg.historical
        ) {
            if (
                !last_msg_container!.status_message &&
                !first_msg_container.msg.is_me_message &&
                same_day(last_msg_container?.msg, first_msg_container.msg) &&
                same_sender(last_msg_container, first_msg_container)
            ) {
                first_msg_container.include_sender = false;
            }
            first_group.message_containers = [
                ...first_group.message_containers,
                ...second_group.message_containers,
            ];
            return true;
        }

        // We may need to add a subscription marker after merging the groups.
        this.maybe_add_subscription_marker_to_group(
            second_group,
            last_msg_container?.msg,
            first_msg_container.msg,
        );

        return false;
    }

    merge_message_groups(new_message_groups: MessageGroup[], where: string): RenderingPlan {
        // merge_message_groups takes a list of new messages groups to add to
        // this._message_groups and a location where to merge them currently
        // top or bottom. It returns an object of changes which needed to be
        // rendered in to the page. The types of actions are append_group,
        // prepend_group, rerender_group, append_message.
        //
        // append_groups are groups to add to the top of the rendered DOM
        // prepend_groups are group to add to the bottom of the rendered DOM
        // rerender_groups are group that should be updated in place in the DOM
        // append_messages are messages which should be added to the last group in the DOM

        const message_actions: RenderingPlan = {
            append_groups: [],
            prepend_groups: [],
            rerender_groups: [],
            append_messages: [],
        };
        let first_group;
        let second_group;

        if (where === "top") {
            first_group = new_message_groups.at(-1);
            second_group = this._message_groups[0];
        } else {
            first_group = this._message_groups.at(-1);
            second_group = new_message_groups[0];
        }

        let prev_msg_container;
        if (first_group) {
            prev_msg_container = first_group.message_containers.at(-1);
        }

        assert(second_group !== undefined);
        const curr_msg_container = second_group.message_containers[0];
        assert(curr_msg_container !== undefined);

        const was_joined = this.join_message_groups(first_group, second_group);
        if (was_joined) {
            update_message_date_divider({
                prev_msg_container,
                curr_msg_container,
            });
        } else {
            clear_message_date_divider(curr_msg_container);
        }

        if (where === "top") {
            assert(first_group !== undefined);
            if (was_joined) {
                // join_message_groups moved the old message to the end of the
                // new group. We need to replace the old rendered message
                // group. So we will reuse its ID.

                first_group.message_group_id = second_group.message_group_id;
                message_actions.rerender_groups.push(first_group);

                // Swap the new group in
                this._message_groups.shift();
                this._message_groups.unshift(first_group);

                new_message_groups = new_message_groups.slice(0, -1);
            } else if (
                !same_day(
                    second_group.message_containers[0]?.msg,
                    first_group.message_containers[0]?.msg,
                )
            ) {
                // The groups did not merge, so we need up update the date row for the old group
                update_group_date(second_group, curr_msg_container.msg, prev_msg_container?.msg);
                // We could add an action to update the date row, but for now rerender the group.
                message_actions.rerender_groups.push(second_group);
            }
            message_actions.prepend_groups = new_message_groups;
            this._message_groups = [...new_message_groups, ...this._message_groups];
        } else {
            if (was_joined) {
                // rerender the last message
                assert(new_message_groups.length > 0);
                message_actions.append_messages = new_message_groups[0]!.message_containers;
                new_message_groups = new_message_groups.slice(1);
            } else if (first_group !== undefined && second_group !== undefined) {
                if (same_day(prev_msg_container?.msg, curr_msg_container.msg)) {
                    clear_group_date(second_group);
                } else {
                    // If we just sent the first message on a new day
                    // in a narrow, make sure we render a date.
                    update_group_date(
                        second_group,
                        curr_msg_container.msg,
                        prev_msg_container?.msg,
                    );
                }
            }
            message_actions.append_groups = new_message_groups;
            this._message_groups = [...this._message_groups, ...new_message_groups];
        }

        return message_actions;
    }

    _put_row($row: JQuery): void {
        // $row is a jQuery object wrapping one message row
        if ($row.hasClass("message_row")) {
            this._rows.set(rows.id($row), $row);
        }
    }

    _post_process($message_rows: JQuery): void {
        // $message_rows wraps one or more message rows

        if (!($message_rows instanceof $)) {
            // An assertion check that we're calling this properly
            blueslip.error("programming error--pass in jQuery objects");
        }

        for (const dom_row of $message_rows) {
            const $row = $(dom_row);
            this._put_row($row);
            this._post_process_single_row($row);
        }

        if (page_params.is_spectator) {
            // For images that fail to load due to being rate limited or being denied access
            // by server in general, we tell user to login to be able to view the image.
            $message_rows.find(".message_inline_image img").on("error", (e) => {
                $(e.target)
                    .closest(".message_inline_image")
                    .replaceWith($(render_login_to_view_image_button()));
            });
        }
    }

    _post_process_single_row($row: JQuery): void {
        // For message formatting that requires some post-processing
        // (and is not possible to handle solely via CSS), this is
        // where we modify the content.  It is a goal to minimize how
        // much logic is present in this function; wherever possible,
        // we should implement features with the Markdown processor,
        // HTML and CSS.

        if ($row.length !== 1) {
            blueslip.error("programming error--expected single element");
        }

        const $content = $row.find(".message_content");

        rendered_markdown.update_elements($content);

        const id = rows.id($row);
        message_edit.maybe_show_edit($row, id);

        submessage.process_submessages({
            $row,
            message_id: id,
        });
    }

    _get_message_template(message_container: MessageContainer): string {
        const msg_reactions = reactions.get_message_reactions(message_container.msg);
        message_container.msg.message_reactions = msg_reactions;
        const msg_to_render = {
            ...message_container,
            message_list_id: this.list.id,
        };
        return render_single_message(msg_to_render);
    }

    _render_group(opts: {message_groups: MessageGroup[]; use_match_properties: boolean}): JQuery {
        const message_groups = opts.message_groups;
        const use_match_properties = opts.use_match_properties;

        return $(
            render_message_group({
                message_groups,
                use_match_properties,
                message_list_id: this.list.id,
            }),
        );
    }

    set_edited_notice_locations(message_container: MessageContainer): void {
        // Based on the variables that define the overall message's HTML layout, set
        // variables defining where the message-edited notices should be placed.
        const include_sender = message_container.include_sender;
        const is_hidden = message_container.is_hidden;
        const status_message = Boolean(message_container.status_message);
        Object.assign(
            message_container,
            this.get_edited_notice_locations(include_sender, is_hidden, status_message),
        );
    }

    get_edited_notice_locations(
        include_sender: boolean,
        is_hidden: boolean,
        status_message: boolean,
    ): {
        message_edit_notices_in_left_col: boolean;
        message_edit_notices_alongside_sender: boolean;
        message_edit_notices_for_status_message: boolean;
    } {
        // Based on the variables that define the overall message's HTML layout, set
        // variables defining where the message-edited notices should be placed.
        return {
            message_edit_notices_in_left_col: !include_sender && !is_hidden,
            message_edit_notices_alongside_sender: include_sender && !status_message,
            message_edit_notices_for_status_message: include_sender && status_message,
        };
    }

    render(
        messages: Message[],
        where: string,
        messages_are_new = false,
    ): {need_user_to_scroll: boolean} | undefined {
        // This function processes messages into chunks with separators between them,
        // and templates them to be inserted as table rows into the DOM.

        if (messages.length === 0) {
            return undefined;
        }

        capture_user_message_editing_state();

        const list = this.list; // for convenience
        let orig_scrolltop_offset: number | undefined;

        // If we start with the message feed scrolled up (i.e.
        // the bottom message is not visible), then we will respect
        // the user's current position after rendering, rather
        // than auto-scrolling.
        const started_scrolled_up = message_viewport.is_scrolled_up();

        for (const message of messages) {
            message.url = hash_util.by_conversation_and_time_url(message);
        }

        const save_scroll_position = (): void => {
            if (orig_scrolltop_offset === undefined && this.selected_row().length > 0) {
                orig_scrolltop_offset = this.selected_row().get_offset_to_window().top;
            }
        };

        const restore_scroll_position = (): void => {
            if (
                narrow_state.is_message_feed_visible() &&
                list === message_lists.current &&
                orig_scrolltop_offset !== undefined
            ) {
                list.view.set_message_offset(orig_scrolltop_offset);
                list.reselect_selected_id();
            }
        };

        const new_message_groups = this.build_message_groups(messages);
        const message_containers = new_message_groups.flatMap((group) => group.message_containers);
        const message_actions = this.merge_message_groups(new_message_groups, where);
        const new_dom_elements = [];
        let $rendered_groups;
        let $dom_messages;
        let $last_message_row;
        let $last_group_row;

        for (const message_container of message_containers) {
            this.set_edited_notice_locations(message_container);
            this.message_containers.set(message_container.msg.id, message_container);
        }

        // Render new message groups on the top
        if (message_actions.prepend_groups.length > 0) {
            save_scroll_position();

            $rendered_groups = this._render_group({
                message_groups: message_actions.prepend_groups,
                use_match_properties: this.list.is_keyword_search(),
            });

            $dom_messages = $rendered_groups.find(".message_row");
            new_dom_elements.push($rendered_groups);

            this._post_process($dom_messages);

            // The date row will be included in the message groups or will be
            // added in a rerendered in the group below
            this.$list.find(".recipient_row").first().prev(".date_row").remove();
            this.$list.prepend($rendered_groups);
            condense.condense_and_collapse($dom_messages);
        }

        // Rerender message groups
        if (message_actions.rerender_groups.length > 0) {
            save_scroll_position();

            for (const message_group of message_actions.rerender_groups) {
                const $old_message_group = $(`#${CSS.escape(message_group.message_group_id)}`);
                // Remove the top date_row, we'll re-add it after rendering
                $old_message_group.prev(".date_row").remove();

                $rendered_groups = this._render_group({
                    message_groups: [message_group],
                    use_match_properties: this.list.is_keyword_search(),
                });

                $dom_messages = $rendered_groups.find(".message_row");
                // Not adding to new_dom_elements it is only used for autoscroll

                this._post_process($dom_messages);
                $old_message_group.replaceWith($rendered_groups);
                condense.condense_and_collapse($dom_messages);
            }
        }

        // Insert new messages in to the last message group
        if (message_actions.append_messages.length > 0) {
            $last_message_row = this.$list.find(".message_row").last().expectOne();
            $last_group_row = rows.get_message_recipient_row($last_message_row);
            $dom_messages = $(
                message_actions.append_messages
                    .map((message_container) => this._get_message_template(message_container))
                    .join(""),
            ).filter(".message_row");

            this._post_process($dom_messages);
            $last_group_row.append($dom_messages);

            condense.condense_and_collapse($dom_messages);
            new_dom_elements.push($dom_messages);
        }

        // Add new message groups to the end
        if (message_actions.append_groups.length > 0) {
            // Remove the trailing bookend; it'll be re-added after we do our rendering
            this.clear_trailing_bookend();

            $rendered_groups = this._render_group({
                message_groups: message_actions.append_groups,
                use_match_properties: this.list.is_keyword_search(),
            });

            $dom_messages = $rendered_groups.find(".message_row");
            new_dom_elements.push($rendered_groups);

            this._post_process($dom_messages);

            // This next line is a workaround for a weird scrolling
            // bug on Chrome.  Basically, in Chrome 64, we had a
            // highly reproducible bug where if you hit the "End" key
            // 5 times in a row in a `near:1` narrow (or any other
            // narrow with enough content below to try this), the 5th
            // time (because RENDER_WINDOW_SIZE / batch_size = 4,
            // i.e. the first time we need to rerender to show the
            // message "End" jumps to) would trigger an unexpected
            // scroll, resulting in some chaotic scrolling and
            // additional fetches (from bottom_whitespace ending up in
            // the view).  During debugging, we found that this adding
            // this next line seems to prevent the Chrome bug from firing.
            message_viewport.scrollTop();

            this.$list.append($rendered_groups);
            condense.condense_and_collapse($dom_messages);
        }

        // After all the messages are rendered, resize any message edit textarea if required.
        autosize.update(this.$list.find(".message_edit_content"));
        maybe_restore_focus_to_message_edit_form();

        restore_scroll_position();

        const last_message_group = this._message_groups.at(-1);
        if (last_message_group !== undefined) {
            list.last_message_historical =
                last_message_group.message_containers.at(-1)!.msg.historical;
        }

        list.update_trailing_bookend();

        if (list === message_lists.current) {
            // Update the fade.

            const get_element = (message_group: MessageGroup): JQuery => {
                // We don't have a MessageGroup class, but we can at least hide the messy details
                // of rows.ts from compose_fade.  We provide a callback function to be lazy--
                // compose_fade may not actually need the elements depending on its internal
                // state.
                const $message_row = this.get_row(message_group.message_containers[0]!.msg.id);
                return rows.get_message_recipient_row($message_row);
            };

            compose_fade.update_rendered_message_groups(new_message_groups, get_element);
        }

        if (list === message_lists.current && messages_are_new) {
            let sent_by_me = false;
            if (messages.some((message) => message.sent_by_me)) {
                sent_by_me = true;
            }
            if (started_scrolled_up) {
                return {
                    need_user_to_scroll: true,
                };
            }
            const new_messages_height = this._new_messages_height(new_dom_elements);
            const need_user_to_scroll = this._maybe_autoscroll(new_messages_height, sent_by_me);

            if (need_user_to_scroll) {
                return {
                    need_user_to_scroll: true,
                };
            }
        }

        return undefined;
    }

    _new_messages_height(rendered_elems: JQuery[]): number {
        let new_messages_height = 0;

        for (const $elem of rendered_elems.reverse()) {
            // Sometimes there are non-DOM elements in rendered_elems; only
            // try to get the heights of actual trs.
            if ($elem.is("div")) {
                new_messages_height += $elem.height()!;
            }
        }

        return new_messages_height;
    }

    _scroll_limit($selected_row: JQuery, viewport_info: MessageViewportInfo): number {
        // This scroll limit is driven by the TOP of the feed, and
        // it's the max amount that we can scroll down (or "skooch
        // up" the messages) before knocking the selected message
        // out of the feed.
        const selected_row_top = $selected_row.get_offset_to_window().top;
        let scroll_limit = selected_row_top - viewport_info.visible_top;

        if (scroll_limit < 0) {
            // This shouldn't happen, but if we're off by a pixel or
            // something, we can deal with it, and just warn.
            blueslip.warn("Selected row appears too high on screen.");
            scroll_limit = 0;
        }

        return scroll_limit;
    }

    _maybe_autoscroll(new_messages_height: number, sent_by_me: boolean): boolean {
        // If we are near the bottom of our feed (the bottom is visible) and can
        // scroll up without moving the pointer out of the viewport, do so, by
        // up to the amount taken up by the new message. For messages sent by
        // the current user, we scroll it into view.
        //
        // returns `true` if we need the user to scroll

        const $selected_row = this.selected_row();
        const $last_visible = rows.last_visible();

        // Make sure we have a selected row and last visible row. (defensive)
        if (!($selected_row && $selected_row.length > 0 && $last_visible)) {
            return false;
        }

        if (new_messages_height <= 0) {
            return false;
        }

        if (!activity.client_is_active) {
            // Don't autoscroll if the window hasn't had focus
            // recently.  This in intended to help protect us from
            // auto-scrolling downwards when the window is in the
            // background and might be having some functionality
            // throttled by modern Chrome's aggressive power-saving
            // features.
            blueslip.log("Suppressing scroll down due to inactivity");
            return false;
        }

        // do not scroll if there are any active popovers.
        if (popovers.any_active() || sidebar_ui.any_sidebar_expanded_as_overlay()) {
            // If a popover is active, then we are pretty sure the
            // incoming message is not from the user themselves, so
            // we don't need to tell users to scroll down.
            return false;
        }

        if (sent_by_me) {
            // For messages sent by the current user we always autoscroll,
            // updating the selected row if needed.
            message_viewport.system_initiated_animate_scroll(new_messages_height, true);
            return false;
        }

        const info = message_viewport.message_viewport_info();
        const scroll_limit = this._scroll_limit($selected_row, info);

        // This next decision is fairly debatable.  For a big message that
        // would push the pointer off the screen, we do a partial autoscroll,
        // which has the following implications:
        //    a) user sees scrolling (good)
        //    b) user's pointer stays on screen (good)
        //    c) scroll amount isn't really tied to size of new messages (bad)
        //    d) all the bad things about scrolling for users who want messages
        //       to stay on the screen
        let scroll_amount;
        let need_user_to_scroll;

        if (new_messages_height <= scroll_limit) {
            // This is the happy path where we can just scroll
            // automatically, and the user will see the new message.
            scroll_amount = new_messages_height;
            need_user_to_scroll = false;
        } else {
            // Sometimes we don't want to scroll the entire height of
            // the message, but our callers can give appropriate
            // warnings if the message is gonna be offscreen.
            // (Even if we are somewhat constrained here, the message may
            // still end up being visible, so we do some arithmetic.)
            scroll_amount = scroll_limit;
            const offset = message_viewport.offset_from_bottom($last_visible);

            // For determining whether we need to show the user a "you
            // need to scroll down" notification, the obvious check
            // would be `offset > scroll_amount`, and that is indeed
            // correct with a 1-line message in the compose box.
            // However, the compose box is open with the content of
            // the message just sent when this code runs, and
            // `offset_from_bottom` if an offset from the top of the
            // compose box, which is about to be reset to empty.  So
            // to compute the offset at the time the user might see
            // this notification, we need to adjust by the amount that
            // the current compose is bigger than the empty, open
            // compose box.
            const compose_textarea_default_height = 42;
            const compose_textarea_current_height = $("textarea#compose-textarea").height()!;
            const expected_change =
                compose_textarea_current_height - compose_textarea_default_height;
            const expected_offset = offset - expected_change;
            need_user_to_scroll = expected_offset > scroll_amount;
        }

        // Ok, we are finally ready to actually scroll.
        if (scroll_amount > 0) {
            message_viewport.system_initiated_animate_scroll(scroll_amount);
        }

        return need_user_to_scroll;
    }

    clear_rendering_state(clear_table: boolean): void {
        if (clear_table) {
            this.clear_table();
        }
        this.list.last_message_historical = false;

        this._render_win_start = 0;
        this._render_win_end = 0;
    }

    update_render_window(selected_idx: number, check_for_changed: boolean): boolean {
        const new_start = Math.max(selected_idx - Math.floor(this._RENDER_WINDOW_SIZE / 2), 0);
        if (check_for_changed && new_start === this._render_win_start) {
            return false;
        }

        this._render_win_start = new_start;
        this._render_win_end = Math.min(
            this._render_win_start + this._RENDER_WINDOW_SIZE,
            this.list.num_items(),
        );
        return true;
    }

    should_fetch_older_messages(): boolean {
        const selected_idx = this.list.selected_idx();
        // We fetch older messages when the user is near the top of the
        // rendered message feed and there are older messages to fetch.
        return (
            // Make sure we have no cached message left to render.
            this._render_win_start === 0 &&
            selected_idx - this._render_win_start < this._RENDER_THRESHOLD &&
            !this.list.data.fetch_status.has_found_oldest()
        );
    }

    should_fetch_newer_messages(): boolean {
        const selected_idx = this.list.selected_idx();
        // We fetch new messages when the user is near the bottom of the
        // rendered message feed and there are newer messages to fetch.
        return (
            // Make sure we have no cached message left to render.
            this._render_win_end === this.list.num_items() &&
            this._render_win_end - selected_idx <= this._RENDER_THRESHOLD &&
            !this.list.data.fetch_status.has_found_newest()
        );
    }

    maybe_rerender(): boolean {
        const selected_idx = this.list.selected_idx();

        // We rerender under the following conditions:
        // * The selected message is within this._RENDER_THRESHOLD messages
        //   of the top of the currently rendered window and the top
        //   of the window does not abut the beginning of the message
        //   list
        // * The selected message is within this._RENDER_THRESHOLD messages
        //   of the bottom of the currently rendered window and the
        //   bottom of the window does not abut the end of the
        //   message list
        if (
            !(
                (selected_idx - this._render_win_start < this._RENDER_THRESHOLD &&
                    this._render_win_start !== 0) ||
                (this._render_win_end - selected_idx <= this._RENDER_THRESHOLD &&
                    this._render_win_end !== this.list.num_items())
            )
        ) {
            return false;
        }

        if (!this.update_render_window(selected_idx, true)) {
            return false;
        }

        this.rerender_preserving_scrolltop();
        return true;
    }

    rerender_preserving_scrolltop(discard_rendering_state = false): void {
        // old_offset is the number of pixels between the top of the
        // viewable window and the selected message
        let old_offset;
        const $selected_row = this.selected_row();
        const selected_in_view = $selected_row.length > 0;
        if (selected_in_view) {
            old_offset = $selected_row.get_offset_to_window().top;
        }
        if (discard_rendering_state) {
            // If we know that the existing render is invalid way
            // (typically because messages appear out-of-order), then
            // we discard the message_list rendering state entirely.
            this.clear_rendering_state(true);
            this.update_render_window(this.list.selected_idx(), false);
        }
        this.rerender_with_target_scrolltop(old_offset);
    }

    set_message_offset(offset: number): void {
        const $msg = this.selected_row();
        assert($msg !== undefined);
        message_viewport.scrollTop($msg.offset()!.top - offset);
    }

    rerender_with_target_scrolltop(target_offset: number | undefined): void {
        // target_offset is the target number of pixels between the top of the
        // viewable window and the selected message
        this.clear_table();
        this.render(
            this.list.all_messages().slice(this._render_win_start, this._render_win_end),
            "bottom",
        );

        // If we could see the newly selected message, scroll the
        // window such that the newly selected message is at the
        // same location as it would have been before we
        // re-rendered.
        if (target_offset !== undefined && message_lists.current === this.list) {
            if (this.selected_row().length === 0 && this.list.selected_id() > -1) {
                this.list.select_id(this.list.selected_id(), {use_closest: true});
            }

            this.set_message_offset(target_offset);
        }
    }

    _find_message_group(message_group_id: string): MessageGroup | undefined {
        // Finds the message group with a given message group ID.
        //
        // This function does a linear search, so be careful to avoid
        // calling it in a loop. If you need that, we'll need to add a
        // hash table to make this O(1) runtime.
        return this._message_groups.find(
            // Since we don't have a way to get a message group from
            // the containing message container, we just do a search
            // to find it.
            (message_group) => message_group.message_group_id === message_group_id,
        );
    }

    _rerender_header(message_containers: MessageContainer[]): void {
        // Given a list of messages that are in the **same** message group,
        // rerender the header / recipient bar of the messages. This method
        // should only be called with rerender_messages as the rerendered
        // header may need to be updated for the "sticky_header" class.
        if (message_containers.length === 0) {
            return;
        }

        const $first_row = this.get_row(message_containers[0]!.msg.id);

        // We may not have the row if the stream or topic was muted
        if ($first_row.length === 0) {
            return;
        }

        const $recipient_row = rows.get_message_recipient_row($first_row);
        const $header = $recipient_row.find(".message_header");
        const message_group_id = $recipient_row.attr("id")!;

        // Since there might be multiple dates within the message
        // group, it's important to look up the original/full message
        // group rather than doing an artificial rerendering of the
        // message header from the set of message containers passed in
        // here.
        const group = this._find_message_group(message_group_id);
        if (group === undefined) {
            blueslip.error("Could not find message group for rerendering headers");
            return;
        }

        // TODO: It's possible that we no longer need this populate
        // call; it was introduced in an earlier version of this code
        // where we constructed an artificial message group for this
        // rerendering rather than looking up the original version.
        const preserved_properties = {
            message_group_id: group.message_group_id,
            message_containers: group.message_containers,
        };
        Object.assign(
            group,
            populate_group_from_message(
                group.message_containers[0]!.msg,
                group.date_unchanged,
                group.message_containers[0]!.year_changed,
                undefined,
            ),
            // We don't want `populate_group_from_message` to generate a
            // new id. We also preserve the message containers, since this
            // function doesn't generate new ones.
            preserved_properties,
        );

        const $rendered_recipient_row = $(render_recipient_row(group));

        $header.replaceWith($rendered_recipient_row);
    }

    _rerender_message(
        message_container: MessageContainer,
        opts: {message_content_edited: boolean; is_revealed: boolean},
    ): void {
        const {message_content_edited, is_revealed} = opts;
        const $row = this.get_row(message_container.msg.id);
        const was_selected = this.list.selected_message() === message_container.msg;

        Object.assign(
            message_container,
            this.get_calculated_message_container_variables(
                message_container.msg,
                message_container.include_sender,
                is_revealed,
            ),
        );

        this.set_edited_notice_locations(message_container);

        const $rendered_msg = $(this._get_message_template(message_container));
        if (message_content_edited) {
            $rendered_msg.addClass("fade-in-message");
        }
        this._post_process($rendered_msg);
        $row.replaceWith($rendered_msg);

        // If this list not currently displayed, we don't need to select the message.
        if (was_selected && this.list === message_lists.current) {
            this.list.reselect_selected_id();
        }
    }

    reveal_hidden_message(message_id: number): void {
        const message_container = this.message_containers.get(message_id);
        assert(message_container !== undefined);
        this._rerender_message(message_container, {
            message_content_edited: false,
            is_revealed: true,
        });
    }

    hide_revealed_message(message_id: number): void {
        const message_container = this.message_containers.get(message_id);
        assert(message_container !== undefined);
        this._rerender_message(message_container, {
            message_content_edited: false,
            is_revealed: false,
        });
    }

    rerender_messages(messages: Message[], message_content_edited = false): void {
        // this.render is never called in this code path, we use
        // `_rerender_message` instead which is optimized for this use
        // case.
        capture_user_message_editing_state();

        // We need to destroy all the tippy instances from the DOM before re-rendering to
        // prevent the appearance of tooltips whose reference has been removed.
        message_list_tooltips.destroy_all_message_list_tooltips();
        // Convert messages to list messages
        const message_containers = [];
        for (const message of messages) {
            const message_container = this.message_containers.get(message.id);
            // We may not have the message_container if the stream or topic was muted
            if (message_container !== undefined) {
                message_containers.push(message_container);
            }
        }

        const message_groups = [];
        let current_group = [];

        for (const message_container of message_containers) {
            if (
                current_group.length === 0 ||
                same_recipient(current_group.at(-1), message_container)
            ) {
                current_group.push(message_container);
            } else {
                message_groups.push(current_group);
                current_group = [];
            }
            this._rerender_message(message_container, {message_content_edited, is_revealed: false});
        }

        if (current_group.length > 0) {
            message_groups.push(current_group);
        }

        for (const messages_in_group of message_groups) {
            this._rerender_header(messages_in_group);
        }

        if (message_lists.current === this.list && narrow_state.is_message_feed_visible()) {
            this.update_sticky_recipient_headers();
            maybe_restore_focus_to_message_edit_form();
        }
    }

    append(
        messages: Message[],
        messages_are_new: boolean,
    ): {need_user_to_scroll: boolean} | undefined {
        const cur_window_size = this._render_win_end - this._render_win_start;
        let render_info;

        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            const slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            render_info = this.render(slice_to_render, "bottom", messages_are_new);
            this._render_win_end += slice_to_render.length;
        }

        // If the pointer is high on the page such that there is a
        // lot of empty space below and the render window is full, a
        // newly received message should trigger a rerender so that
        // the new message, which will appear in the viewable area,
        // is rendered.
        const needed_rerender = this.maybe_rerender();

        if (needed_rerender) {
            render_info = {need_user_to_scroll: true};
        }

        return render_info;
    }

    prepend(messages: Message[]): void {
        if (this._render_win_end - this._render_win_start === 0) {
            // If the message list previously contained no visible
            // messages, appending and prepending are equivalent, but
            // the prepend logic will throw an exception, so just
            // handle this as an append request.
            //
            // This is somewhat hacky, but matches how we do rendering
            // for the first messages in a new msg_list_data object.
            this.append(messages, false);
            return;
        }

        // If we already have some messages rendered, then prepending
        // will effectively change the meaning of the existing
        // numbers.
        this._render_win_start += messages.length;
        this._render_win_end += messages.length;

        const cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            const msgs_to_render_count = this._RENDER_WINDOW_SIZE - cur_window_size;
            const slice_to_render = messages.slice(messages.length - msgs_to_render_count);
            this.render(slice_to_render, "top", false);
            this._render_win_start -= slice_to_render.length;
        }

        // See comment for maybe_rerender call in the append code path
        this.maybe_rerender();
    }

    clear_table(): void {
        capture_user_message_editing_state();
        // We do not want to call .empty() because that also clears
        // jQuery data.  This does mean, however, that we need to be
        // mindful of memory leaks.
        this.$list.children().detach();
        this._rows.clear();
        this._message_groups = [];
        this.message_containers.clear();
    }

    last_rendered_message(): Message | undefined {
        return this.list.data._items[this._render_win_end - 1];
    }

    is_fetched_end_rendered(): boolean {
        return this._render_win_end === this.list.num_items();
    }

    is_end_rendered(): boolean {
        // Used as a helper in checks for whether a given scroll
        // position is actually the very end of this view. It could
        // fail to be for two reasons: Either some newer messages are
        // not rendered due to a render window, or we haven't finished
        // fetching the newest messages for this view from the server.
        return this.is_fetched_end_rendered() && this.list.data.fetch_status.has_found_newest();
    }

    first_rendered_message(): Message | undefined {
        return this.list.data._items[this._render_win_start];
    }

    is_fetched_start_rendered(): boolean {
        return this._render_win_start === 0;
    }

    is_start_rendered(): boolean {
        // Used as a helper in checks for whether a given scroll
        // position is actually the very start of this view. It could
        // fail to be for two reasons: Either some older messages are
        // not rendered due to a render window, or we haven't finished
        // fetching the oldest messages for this view from the server.
        return this.is_fetched_start_rendered() && this.list.data.fetch_status.has_found_oldest();
    }

    get_row(id: number): JQuery {
        const $row = this._rows.get(id);

        if ($row === undefined) {
            // For legacy reasons we need to return an empty
            // jQuery object here.
            return $();
        }

        return $row;
    }

    clear_trailing_bookend(): void {
        const $trailing_bookend = this.$list.find(".trailing_bookend");
        $trailing_bookend.remove();
    }

    render_trailing_bookend(
        stream_id: number,
        stream_name: string | undefined,
        subscribed: boolean,
        deactivated: boolean,
        just_unsubscribed: boolean,
        is_spectator: boolean,
        invite_only: boolean,
        is_web_public: boolean,
    ): void {
        // This is not the only place we render bookends; see also the
        // partial in message_group.hbs, which do not set is_trailing_bookend.
        const $rendered_trailing_bookend = $(
            render_bookend({
                stream_id,
                stream_name,
                subscribed,
                deactivated,
                just_unsubscribed,
                is_spectator,
                is_trailing_bookend: true,
                invite_only,
                is_web_public,
            }),
        );
        this.$list.append($rendered_trailing_bookend);
    }

    selected_row(): JQuery {
        return this.get_row(this.list.selected_id());
    }

    get_message(id: number): Message | undefined {
        return this.list.get(id);
    }

    change_message_id(old_id: number, new_id: number): void {
        if (this._rows.has(old_id)) {
            const $row = this._rows.get(old_id);
            assert($row !== undefined);
            this._rows.delete(old_id);

            $row.attr("data-message-id", new_id);
            $row.attr("id", `message-row-${this.list.id}-` + new_id);
            $row.removeClass("local");
            this._rows.set(new_id, $row);
        }

        if (this.message_containers.has(old_id)) {
            const message_container = this.message_containers.get(old_id);
            assert(message_container !== undefined);
            this.message_containers.delete(old_id);
            this.message_containers.set(new_id, message_container);
        }
    }

    _maybe_get_me_message(
        is_hidden: boolean,
        message: Message,
    ): {
        status_message: string | false;
        include_sender?: boolean;
    } {
        // If the message is to be hidden anyway, no need to render
        // it differently.
        if (!is_hidden && message.is_me_message) {
            // Slice the '<p>/me ' off the front, and '</p>' off the first line
            // 'p' tag is sliced off to get sender in the same line as the
            // first line of the message
            const msg_content = message.content;
            const p_index = msg_content.indexOf("</p>");
            return {
                status_message:
                    msg_content.slice("<p>/me ".length, p_index) +
                    msg_content.slice(p_index + "</p>".length),
                include_sender: true,
            };
        }
        return {
            status_message: false,
        };
    }

    /* This function exist for two purposes:
        * To track the current `sticky_header` which have some different properties
          like date being always displayed.
        * Set date on message header corresponding to the message next to the header. */
    update_sticky_recipient_headers(): void {
        const rows_length = this._rows.size;
        if (!rows_length) {
            /* No headers are present */
            return;
        }

        const dom_updates: {
            add_classes: {
                $element: JQuery;
                class: string;
            }[];
            remove_classes: {
                $element: JQuery;
                class: string;
            }[];
            html_updates: {
                $element: JQuery;
                rendered_date: string | HTMLElement;
            }[];
        } = {
            add_classes: [],
            remove_classes: [],
            html_updates: [],
        };

        const $current_sticky_header = $(".sticky_header");
        if ($current_sticky_header.length === 1) {
            // Reset the date on the header in case we changed it.
            const message_group_id = rows
                .get_message_recipient_row($current_sticky_header)
                .attr("id")!;
            const group = this._find_message_group(message_group_id);
            if (group !== undefined) {
                const rendered_date = group.date;
                dom_updates.html_updates.push({
                    $element: $current_sticky_header.find(".recipient_row_date"),
                    rendered_date,
                });
            }
            dom_updates.remove_classes.push({
                $element: $current_sticky_header,
                class: "sticky_header",
            });
        }

        const navbar_bottom = $("#navbar-fixed-container").outerHeight()!;
        /* We need date to be properly visible on the header, so partially visible headers
           who are about to be scrolled out of view are not acceptable. */
        const partially_hidden_header_position = navbar_bottom - 1;

        function is_sticky(header: Element): number {
            // header has a box-shadow of `1px` at top but since it doesn't impact
            // `y` position of the header, we don't take it into account during calculations.
            const header_props = header.getBoundingClientRect();
            // This value is dependent upon space between two `recipient_row` message groups.
            const margin_between_recipient_rows = 10;
            const sticky_or_about_to_be_sticky_header_position =
                navbar_bottom + header_props.height + margin_between_recipient_rows;
            if (header_props.top < partially_hidden_header_position) {
                return -1;
            } else if (header_props.top > sticky_or_about_to_be_sticky_header_position) {
                return 1;
            }
            /* Headers between `partially_hidden_header_position` and `sticky_or_about_to_be_sticky_header_position`
               are sticky. If two headers next to each other are completely visible
               (message header at top has no visible content), we don't mind showing
               date on any of them. Which header is chosen will depend on which
               comes first when iterating on the headers. */
            return 0;
        }

        const $headers = this.$list.find(".message_header");
        const iterable_headers = $headers.toArray();
        let start = 0;
        let end = iterable_headers.length - 1;
        let $sticky_header; // This is the first fully visible message header.

        /* Binary search to reach the sticky header */
        while (start <= end) {
            const mid = Math.floor((start + end) / 2);
            const header = iterable_headers[mid]!;
            const diff = is_sticky(header);
            if (diff === 0) {
                $sticky_header = $(header);
                break;
            } else if (diff === 1) {
                end = mid - 1;
            } else {
                start = mid + 1;
            }
        }
        /* Set correct date for the sticky_header. */
        let $message_row;
        if (!$sticky_header) {
            /* If the user is at the top of the scroll container,
               the header is visible for the first message group, and we can display the date for the first visible message.
               We don't need to add `sticky_header` class here since date is already visible
               and header is not truly sticky at top of screen yet. */
            $sticky_header = $headers.first();
            $message_row = $sticky_header.nextAll(".message_row").first();
        } else {
            dom_updates.add_classes.push({$element: $sticky_header, class: "sticky_header"});
            const sticky_header_props = util.the($sticky_header).getBoundingClientRect();
            /* date separator starts to be hidden at this height difference. */
            const date_separator_padding = 7;
            const sticky_header_bottom = sticky_header_props.top + sticky_header_props.height;
            const possible_new_date_separator_start = sticky_header_bottom - date_separator_padding;
            /* Get `message_row` under the sticky header. */
            const elements_below_sticky_header = document.elementsFromPoint(
                sticky_header_props.left,
                possible_new_date_separator_start,
            );
            const message_rows = elements_below_sticky_header
                .filter((element) => element instanceof HTMLElement)
                .filter((element) => element.classList.contains("message_row"))
                .filter((element) => !rows.is_overlay_row($(element)));
            if (message_rows.length === 0) {
                /* If there is no message row under the header, it means it is not sticky yet,
                   so we just get the message next to the header. */
                $message_row = $sticky_header.nextAll(".message_row").first();
            } else {
                $message_row = $(message_rows[0]!);
            }
        }
        // We expect message information to be available for the message row even for failed or
        // local echo messages. If for some reason we don't have the data for message row, we can't
        // update the sticky header date or identify the message under it for other use cases.
        this.sticky_recipient_message_id = undefined;
        const msg_id = rows.id($message_row);
        if (msg_id === undefined) {
            blueslip.error(`Missing message id for sticky recipient row.`);
            return;
        }
        const message = message_store.get(msg_id);
        if (!message) {
            blueslip.error(
                `Message not found for the message id identified for sticky header: ${msg_id}.`,
            );
            return;
        }
        this.sticky_recipient_message_id = message.id;
        const time = new Date(message.timestamp * 1000);
        const message_container = this.message_containers.get(message.id)!;
        const rendered_date = timerender.render_date(time, message_container.year_changed);
        dom_updates.html_updates.push({
            $element: $sticky_header.find(".recipient_row_date"),
            rendered_date,
        });

        // The following prevents a broken looking situation where
        // there's a recipient row (possibly partially) visible just
        // above the sticky recipient row, with an identical
        // date. (E.g., both displaying "today"). We avoid this by
        // hiding the date display on the non-sticky previous
        // recipient row.
        dom_updates.remove_classes.push({
            $element: $(".hide-date-separator-header"),
            class: "hide-date-separator-header",
        });
        // This corner case only occurs when the date is unchanged
        // from the previous recipient row.
        if ($sticky_header.find(".recipient_row_date.recipient_row_date_unchanged").length > 0) {
            const $prev_recipient_row = $sticky_header
                .closest(".recipient_row")
                .prev(".recipient_row");
            if ($prev_recipient_row.length === 0) {
                return;
            }
            const $prev_header_date_row = $prev_recipient_row.find(".recipient_row_date");
            // Check if the recipient row before sticky header is a date separator.
            if (!$prev_header_date_row.hasClass("recipient_row_date_unchanged")) {
                dom_updates.add_classes.push({
                    $element: $prev_header_date_row,
                    class: "hide-date-separator-header",
                });
            }
        }

        // Apply all the updates to the DOM at the end for improved performance.
        for (const update of dom_updates.remove_classes) {
            update.$element.removeClass(update.class);
        }
        for (const update of dom_updates.add_classes) {
            update.$element.addClass(update.class);
        }
        for (const update of dom_updates.html_updates) {
            const rendered_date = update.rendered_date;
            update.$element.html(rendered_date);
        }
    }

    update_recipient_bar_background_color(): void {
        const $stream_headers = this.$list.find(".message_header_stream");
        for (const stream_header of $stream_headers) {
            const $stream_header = $(stream_header);
            stream_color.update_stream_recipient_color($stream_header);
        }
    }

    show_message_as_read(message: Message, options: {from?: "pointer" | "server"}): void {
        const $row = this.get_row(message.id);
        if (options.from === "pointer" || options.from === "server") {
            $row.find(".unread_marker").addClass("fast_fade");
        } else {
            $row.find(".unread_marker").addClass("slow_fade");
        }
        $row.removeClass("unread");
    }

    show_messages_as_unread(message_ids: number[]): void {
        const $rows_to_show_as_unread = this.$list.find(".message_row").filter((_index, $row) => {
            // eslint-disable-next-line unicorn/prefer-dom-node-dataset
            const message_id = Number.parseFloat($row.getAttribute("data-message-id")!);
            return message_ids.includes(message_id);
        });
        $rows_to_show_as_unread.addClass("unread");
    }
}
