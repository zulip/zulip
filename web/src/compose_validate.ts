import $ from "jquery";
import _ from "lodash";
import type {ReferenceElement} from "tippy.js";

import * as resolved_topic from "../shared/src/resolved_topic.ts";
import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_compose_mention_group_warning from "../templates/compose_banner/compose_mention_group_warning.hbs";
import render_guest_in_dm_recipient_warning from "../templates/compose_banner/guest_in_dm_recipient_warning.hbs";
import render_not_subscribed_warning from "../templates/compose_banner/not_subscribed_warning.hbs";
import render_private_stream_warning from "../templates/compose_banner/private_stream_warning.hbs";
import render_stream_wildcard_warning from "../templates/compose_banner/stream_wildcard_warning.hbs";
import render_topic_moved_banner from "../templates/compose_banner/topic_moved_banner.hbs";
import render_wildcard_mention_not_allowed_error from "../templates/compose_banner/wildcard_mention_not_allowed_error.hbs";
import render_compose_limit_indicator from "../templates/compose_limit_indicator.hbs";
import render_topics_required_error_message from "../templates/topics_required_error_message.hbs";

import * as blueslip from "./blueslip.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_store from "./message_store.ts";
import * as message_util from "./message_util.ts";
import * as narrow_state from "./narrow_state.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as reactions from "./reactions.ts";
import * as recent_senders from "./recent_senders.ts";
import * as settings_data from "./settings_data.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import type {UserOrMention} from "./typeahead_helper.ts";
import {toggle_user_group_info_popover} from "./user_group_popover.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as util from "./util.ts";

let user_acknowledged_stream_wildcard = false;
let upload_in_progress = false;
let no_message_content = false;
let message_too_long = false;
// Since same functions are used for both compose and message edit,
//  we need to track when we are validating compose box.
let is_validating_compose_box = false;
let disabled_send_tooltip_message_html = "";
let posting_policy_error_message = "";

export const NO_PERMISSION_TO_POST_IN_CHANNEL_ERROR_MESSAGE = $t({
    defaultMessage: "You do not have permission to post in this channel.",
});
export const NO_PRIVATE_RECIPIENT_ERROR_MESSAGE = $t({
    defaultMessage: "Please add a valid recipient.",
});
export const NO_CHANNEL_SELECTED_ERROR_MESSAGE = $t({defaultMessage: "Please select a channel."});
export const get_topics_required_error_message_html = (): string =>
    render_topics_required_error_message({
        empty_string_topic_display_name: util.get_final_topic_display_name(""),
    });
export const get_message_too_long_for_compose_error = (): string =>
    $t(
        {defaultMessage: `Message length shouldn't be greater than {max_length} characters.`},
        {max_length: realm.max_message_length},
    );
export const NO_MESSAGE_CONTENT_ERROR_MESSAGE = $t({defaultMessage: "Compose a message."});
export const UNSUBSCRIBED_CHANNEL_ERROR_MESSAGE = $t({
    defaultMessage:
        "You're not subscribed to this channel. You will not be notified if other users reply to your message.",
});
export const CHANNEL_WILDCARD_ACKNOWLEDGE_MISSING_ERROR_TOOLTIP_MESSAGE = $t({
    defaultMessage: "Please acknowledge the warning to send the message.",
});

// Only used in tooltips.
export const INVALID_CHANNEL_ERROR_TOOLTIP_MESSAGE = $t({
    defaultMessage: "Please select a valid channel.",
});
export const UPLOAD_IN_PROGRESS_ERROR_TOOLTIP_MESSAGE = $t({
    defaultMessage: "Cannot send message while files are being uploaded.",
});
export const WILDCARD_MENTION_ERROR_TOOLTIP_MESSAGE = $t({
    defaultMessage: "You do not have permission to use wildcard mentions in large streams.",
});

type StreamWildcardOptions = {
    stream_id: number;
    $banner_container: JQuery;
    scheduling_message: boolean;
    stream_wildcard_mention: string | null;
};

export let wildcard_mention_threshold = 15;

export function set_upload_in_progress(status: boolean): void {
    upload_in_progress = status;
    validate_and_update_send_button_status();
}

function set_no_message_content(status: boolean): void {
    no_message_content = status;
}

function set_message_too_long_for_compose(status: boolean): void {
    message_too_long = status;
}

function set_message_too_long_for_edit(status: boolean, $container: JQuery): void {
    const message_too_long = status;
    const $message_edit_save_container = $container.find(".message_edit_save_container");
    $message_edit_save_container.toggleClass("message-too-long-for-edit", message_too_long);
    const save_is_disabled =
        message_too_long ||
        $message_edit_save_container.hasClass("message-edit-time-limit-expired");

    $container.find(".message_edit_save").prop("disabled", save_is_disabled);
    $message_edit_save_container.toggleClass("disabled-message-edit-save", save_is_disabled);
}

export function get_posting_policy_error_message(): string {
    // Contains errors which are shown as compose banner before user
    // clicks on the send button.
    // Ensure you are calling `validate` for the current compose state,
    // before calling this function.
    // We directly add the error banner instead of setting
    // `posting_policy_error_message`, when the banner contains special
    // context for the current compose state.
    return posting_policy_error_message;
}

export function get_disabled_send_tooltip_html(): string {
    return disabled_send_tooltip_message_html;
}

export function get_disabled_save_tooltip($container: JQuery): string {
    const $button_wrapper = $container.find(".message_edit_save_container");
    // The time limit expiry tooltip takes precedence over the message
    // length exceeded tooltip.
    if ($button_wrapper.hasClass("message-edit-time-limit-expired")) {
        return $t({
            defaultMessage: "You can no longer save changes to this message.",
        });
    }
    if ($button_wrapper.hasClass("message-too-long-for-edit")) {
        return get_message_too_long_for_compose_error();
    }
    return "";
}

export async function needs_subscribe_warning(
    user_id: number,
    stream_id: number,
): Promise<boolean> {
    // This returns true if all of these conditions are met:
    //  * the user is valid
    //  * the user is not already subscribed to the stream
    //  * the user has no back-door way to see stream messages
    //    (i.e. bots on public/private streams)
    //
    //  You can think of this as roughly answering "is there an
    //  actionable way to subscribe the user and do they actually
    //  need it?".
    //
    //  We expect the caller to already have verified that we're
    //  sending to a valid stream and trying to mention the user.

    const user = people.maybe_get_user_by_id(user_id);

    if (!user) {
        return false;
    }

    if (user.is_bot) {
        // Bots may receive messages on public/private streams even if they are
        // not subscribed.
        return false;
    }

    if (await stream_data.maybe_fetch_is_user_subscribed(stream_id, user_id, false)) {
        // If our user is already subscribed
        return false;
    }

    return true;
}

export function check_dm_permissions_and_get_error_string(user_ids_string: string): string {
    if (!people.user_can_direct_message(user_ids_string)) {
        if (user_groups.is_setting_group_empty(realm.realm_direct_message_permission_group)) {
            return $t({
                defaultMessage: "Direct messages are disabled in this organization.",
            });
        }
        return $t({
            defaultMessage: "This conversation does not include any users who can authorize it.",
        });
    }
    if (
        message_util.get_direct_message_permission_hints(user_ids_string)
            .is_known_empty_conversation &&
        !people.user_can_initiate_direct_message_thread(user_ids_string)
    ) {
        return $t({
            defaultMessage: "You are not allowed to start direct message conversations.",
        });
    }
    return "";
}

function get_stream_id_for_textarea($textarea: JQuery<HTMLTextAreaElement>): number | undefined {
    // Returns the stream ID, if any, associated with the textarea:
    // The recipient of a message being edited, or the target
    // recipient of a message being drafted in the compose box.
    // Returns undefined if the appropriate context is a direct
    // message conversation.
    const is_in_editing_area = $textarea.closest(".message_row").length > 0;

    if (is_in_editing_area) {
        const stream_id_str = $textarea
            .closest(".recipient_row")
            .find(".message_header")
            .attr("data-stream-id");
        if (stream_id_str === undefined) {
            // Direct messages don't have a data-stream-id.
            return undefined;
        }
        return Number.parseInt(stream_id_str, 10);
    }

    return compose_state.stream_id();
}

export async function warn_if_private_stream_is_linked(
    linked_stream: StreamSubscription,
    $textarea: JQuery<HTMLTextAreaElement>,
): Promise<void> {
    const stream_id = get_stream_id_for_textarea($textarea);

    if (!stream_id) {
        // There are two cases in which the `stream_id` will be
        // omitted, and we want to exclude the warning banner:
        //
        // 1. We currently do not warn about links to private streams
        // in direct messages; it would probably be an improvement to
        // do so when one of the recipients is not subscribed.
        //
        // 2. If we have an invalid stream name, we do not warn about
        // it here; we will show an error to the user when they try to
        // send the message.
        return;
    }

    // If the stream we're linking to is not invite-only, then it's
    // public, and there is no need to warn about it, since all
    // members can already see all the public streams.
    //
    // Theoretically, we could still do a warning if there are any
    // guest users subscribed to the stream we're posting to; we may
    // change this policy if user feedback suggests it'd be an
    // improvement.
    if (!linked_stream.invite_only) {
        return;
    }

    // Don't warn if subscribers list of current compose_stream is
    // a subset of linked_stream's subscribers list, because
    // everyone will be subscribed to the linked stream and so
    // knows it exists.  (But always warn Zephyr users, since
    // we may not know their stream's subscribers.)
    // Note: `is_subscriber_subset` can return `null` if we encounter
    // an error fetching subscriber data. In that case, we just show
    // the banner.
    if (
        (await peer_data.is_subscriber_subset(stream_id, linked_stream.stream_id)) &&
        !realm.realm_is_zephyr_mirror_realm
    ) {
        return;
    }

    // If we've changed streams since fetching subscriber data,
    // don't update the UI anymore.
    // Note: The user might have removed the mention of the private
    // stream during the fetch, and in that case the banner will
    // still (possibly) show up. If we add logic in the future to
    // remove banners as the user edits their message, we could use
    // that here as well.
    if (stream_id !== get_stream_id_for_textarea($textarea)) {
        return;
    }

    const $banner_container = compose_banner.get_compose_banner_container($textarea);
    const $existing_stream_warnings_area = $banner_container.find(
        `.${CSS.escape(compose_banner.CLASSNAMES.private_stream_warning)}`,
    );

    const existing_stream_warnings = [...$existing_stream_warnings_area].map((stream_row) =>
        Number($(stream_row).attr("data-stream-id")),
    );

    if (!existing_stream_warnings.includes(linked_stream.stream_id)) {
        const new_row_html = render_private_stream_warning({
            stream_id: linked_stream.stream_id,
            banner_type: compose_banner.WARNING,
            channel_name: linked_stream.name,
            classname: compose_banner.CLASSNAMES.private_stream_warning,
        });
        compose_banner.append_compose_banner_to_banner_list($(new_row_html), $banner_container);
    }
}

export async function warn_if_mentioning_unsubscribed_user(
    mentioned: UserOrMention,
    $textarea: JQuery<HTMLTextAreaElement>,
): Promise<void> {
    // Disable for Zephyr mirroring realms, since we never have subscriber lists there
    if (realm.realm_is_zephyr_mirror_realm) {
        return;
    }

    if (mentioned.type === "broadcast") {
        return; // don't check if @all/@everyone/@stream
    }
    const user_id = mentioned.user.user_id;

    const stream_id = get_stream_id_for_textarea($textarea);
    if (!stream_id) {
        return;
    }

    if (await needs_subscribe_warning(user_id, stream_id)) {
        // Double check that we're still composing to the same stream id
        // after the awaited fetch for subscriber data.
        if (get_stream_id_for_textarea($textarea) !== stream_id) {
            return;
        }

        const $banner_container = compose_banner.get_compose_banner_container($textarea);
        const $existing_invites_area = $banner_container.find(
            `.${CSS.escape(compose_banner.CLASSNAMES.recipient_not_subscribed)}`,
        );

        const existing_invites = [...$existing_invites_area].map((user_row) =>
            Number($(user_row).attr("data-user-id")),
        );
        const sub = stream_data.get_sub_by_id(stream_id)!;
        const can_subscribe_other_users = stream_data.can_subscribe_others(sub);

        if (!existing_invites.includes(user_id)) {
            const context = {
                user_id,
                stream_id,
                banner_type: compose_banner.WARNING,
                button_text: can_subscribe_other_users
                    ? $t({defaultMessage: "Subscribe them"})
                    : null,
                can_subscribe_other_users,
                name: mentioned.user.full_name,
                classname: compose_banner.CLASSNAMES.recipient_not_subscribed,
                should_add_guest_user_indicator: people.should_add_guest_user_indicator(user_id),
            };

            const new_row_html = render_not_subscribed_warning(context);
            const $container = compose_banner.get_compose_banner_container($textarea);
            compose_banner.append_compose_banner_to_banner_list($(new_row_html), $container);
        }
    }
}

export async function warn_if_mentioning_unsubscribed_group(
    mentioned_group: UserGroup,
    $textarea: JQuery<HTMLTextAreaElement>,
    is_silent: boolean,
): Promise<void> {
    if (is_silent) {
        return;
    }

    const stream_id = get_stream_id_for_textarea($textarea);
    if (!stream_id) {
        return;
    }

    const group_members = user_groups.get_recursive_group_members(mentioned_group);
    let any_member_subscribed = false;
    for (const user_id of group_members) {
        if (
            (await stream_data.maybe_fetch_is_user_subscribed(stream_id, user_id, false)) &&
            people.is_person_active(user_id)
        ) {
            any_member_subscribed = true;
            break;
        }
    }
    if (any_member_subscribed) {
        return;
    }

    // Double check that we're still composing to the same stream id
    // after the awaited fetches for subscriber data.
    if (get_stream_id_for_textarea($textarea) !== stream_id) {
        return;
    }

    const $banner_container = compose_banner.get_compose_banner_container($textarea);

    // Check if a banner for this specific group already exists
    const $existing_banners = $banner_container.find(
        `.${CSS.escape(compose_banner.CLASSNAMES.group_entirely_not_subscribed)} a[data-user-group-id="${mentioned_group.id}"]`,
    );
    if ($existing_banners.length > 0) {
        return; // Avoid duplicate banners
    }

    const context = {
        group_id: mentioned_group.id,
        group_name: mentioned_group.name,
        banner_type: compose_banner.WARNING,
        classname: compose_banner.CLASSNAMES.group_entirely_not_subscribed,
    };
    const new_row_html = render_compose_mention_group_warning(context);
    compose_banner.append_compose_banner_to_banner_list($(new_row_html), $banner_container);
}

// Called when clearing the compose box and similar contexts to clear
// the warning for composing to a resolved topic, if present. Also clears
// the state for whether this warning has already been shown in the
// current narrow.
export function clear_topic_resolved_warning(): void {
    compose_state.set_recipient_viewed_topic_resolved_banner(false);
    $(`#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.topic_resolved)}`).remove();
}

export function warn_if_topic_resolved(topic_changed: boolean): void {
    // This function is called with topic_changed=false on every
    // keypress when typing a message, so it should not do anything
    // expensive in that case.
    //
    // Pass topic_changed=true if this function was called in response
    // to a topic being edited.

    const stream_id = compose_state.stream_id();
    if (stream_id === undefined) {
        return;
    }

    const topic_name = compose_state.topic();
    if (!topic_changed && !resolved_topic.is_resolved(topic_name)) {
        // The resolved topic warning will only ever appear when
        // composing to a resolve topic, so we return early without
        // inspecting additional fields in this case.
        return;
    }

    const message_content = compose_state.message_content();
    const sub = stream_data.get_sub_by_id(stream_id);
    if (sub && message_content !== "" && resolved_topic.is_resolved(topic_name)) {
        if (compose_state.has_recipient_viewed_topic_resolved_banner()) {
            // We display the resolved topic banner at most once per narrow.
            return;
        }

        const button_text = settings_data.user_can_resolve_topic()
            ? $t({defaultMessage: "Unresolve topic"})
            : null;

        const context = {
            banner_type: compose_banner.WARNING,
            stream_id: sub.stream_id,
            topic_name,
            banner_text: $t({
                defaultMessage:
                    "You are sending a message to a resolved topic. You can send as-is or unresolve the topic first.",
            }),
            button_text,
            classname: compose_banner.CLASSNAMES.topic_resolved,
        };

        const new_row_html = render_compose_banner(context);
        const appended = compose_banner.append_compose_banner_to_banner_list(
            $(new_row_html),
            $("#compose_banners"),
        );
        if (appended) {
            compose_state.set_recipient_viewed_topic_resolved_banner(true);
        }
    } else {
        clear_topic_resolved_warning();
    }
}

export function clear_topic_moved_info(): void {
    compose_state.set_recipient_viewed_topic_moved_banner(false);
    $(`#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.topic_is_moved)}`).remove();
}

export function inform_if_topic_is_moved(orig_topic: string, old_stream_id: number): void {
    const stream_id = compose_state.stream_id();
    if (stream_id === undefined) {
        return;
    }
    const message_content = compose_state.message_content();
    const sub = stream_data.get_sub_by_id(stream_id);
    const topic_name = compose_state.topic();
    if (sub && message_content !== "") {
        const old_stream = stream_data.get_sub_by_id(old_stream_id);
        if (!old_stream) {
            return;
        }

        let is_empty_string_topic;
        if (orig_topic !== "") {
            is_empty_string_topic = false;
        } else {
            is_empty_string_topic = true;
        }
        const narrow_url = hash_util.by_stream_topic_url(old_stream_id, orig_topic);
        const context = {
            banner_type: compose_banner.INFO,
            stream_id: sub.stream_id,
            topic_name,
            narrow_url,
            orig_topic,
            old_stream: old_stream.name,
            classname: compose_banner.CLASSNAMES.topic_is_moved,
            show_colored_icon: false,
            is_empty_string_topic,
        };
        const new_row_html = render_topic_moved_banner(context);

        if (compose_state.has_recipient_viewed_topic_moved_banner()) {
            // Replace any existing banner of this type to avoid showing
            // two banners if a conversation is moved twice in quick succession.
            clear_topic_moved_info();
        }

        const appended = compose_banner.append_compose_banner_to_banner_list(
            $(new_row_html),
            $("#compose_banners"),
        );
        if (appended) {
            compose_state.set_recipient_viewed_topic_moved_banner(true);
        }
    } else {
        clear_topic_moved_info();
    }
}

export function warn_if_in_search_view(): void {
    const filter = narrow_state.filter();
    if (filter && !filter.supports_collapsing_recipients()) {
        const context = {
            banner_type: compose_banner.WARNING,
            banner_text: $t({
                defaultMessage:
                    "This conversation may have additional messages not shown in this view.",
            }),
            button_text: $t({defaultMessage: "Go to conversation"}),
            classname: compose_banner.CLASSNAMES.search_view,
        };

        const new_row_html = render_compose_banner(context);
        compose_banner.append_compose_banner_to_banner_list($(new_row_html), $("#compose_banners"));
    }
}

export function clear_guest_in_dm_recipient_warning(): void {
    // We don't call set_recipient_guest_ids_for_dm_warning here, so
    // that reopening the same draft won't make the banner reappear.
    const classname = compose_banner.CLASSNAMES.guest_in_dm_recipient_warning;
    $(`#compose_banners .${CSS.escape(classname)}`).remove();
}

// Only called on recipient change. Adds new banner if not already
// exists or updates the existing banner or removes banner if no
// guest in the dm.
export function warn_if_guest_in_dm_recipient(): void {
    if (!compose_state.composing()) {
        return;
    }
    const recipient_ids = compose_pm_pill.get_user_ids();
    const guest_ids = people.filter_other_guest_ids(recipient_ids);

    if (
        !realm.realm_enable_guest_user_dm_warning ||
        compose_state.get_message_type() !== "private" ||
        guest_ids.length === 0
    ) {
        clear_guest_in_dm_recipient_warning();
        compose_state.set_recipient_guest_ids_for_dm_warning([]);
        return;
    }
    // If warning was shown earlier for same guests in the recipients, do nothing.
    if (_.isEqual(compose_state.get_recipient_guest_ids_for_dm_warning(), guest_ids)) {
        return;
    }

    const guest_names = people.user_ids_to_full_names_array(guest_ids);
    let banner_text: string;

    if (guest_names.length === 1) {
        banner_text = $t(
            {defaultMessage: "{name} is a guest in this organization."},
            {name: guest_names[0]},
        );
    } else {
        const names_string = util.format_array_as_list(guest_names, "long", "conjunction");
        banner_text = $t(
            {defaultMessage: "{names} are guests in this organization."},
            {names: names_string},
        );
    }

    const classname = compose_banner.CLASSNAMES.guest_in_dm_recipient_warning;
    let $banner = $(`#compose_banners .${CSS.escape(classname)}`);

    compose_state.set_recipient_guest_ids_for_dm_warning(guest_ids);
    // Update banner text if banner already exists.
    if ($banner.length === 1) {
        $banner.find(".banner_content").text(banner_text);
        return;
    }

    $banner = $(
        render_guest_in_dm_recipient_warning({
            banner_text,
            classname: compose_banner.CLASSNAMES.guest_in_dm_recipient_warning,
        }),
    );
    compose_banner.append_compose_banner_to_banner_list($banner, $("#compose_banners"));
}

function show_stream_wildcard_warnings(opts: StreamWildcardOptions): void {
    const subscriber_count = peer_data.get_subscriber_count(opts.stream_id) || 0;
    const stream_name = sub_store.maybe_get_stream_name(opts.stream_id);
    const is_edit_container = opts.$banner_container.closest(".edit_form_banners").length > 0;
    const classname = compose_banner.CLASSNAMES.wildcard_warning;

    let button_text = opts.scheduling_message
        ? $t({defaultMessage: "Yes, schedule"})
        : $t({defaultMessage: "Yes, send"});

    if (is_edit_container) {
        button_text = $t({defaultMessage: "Yes, save"});
    }

    const stream_wildcard_html = render_stream_wildcard_warning({
        banner_type: compose_banner.WARNING,
        subscriber_count,
        channel_name: stream_name,
        wildcard_mention: opts.stream_wildcard_mention,
        button_text,
        hide_close_button: true,
        classname,
        scheduling_message: opts.scheduling_message,
    });

    // only show one error for any number of @all or @everyone mentions
    if (opts.$banner_container.find(`.${CSS.escape(classname)}`).length === 0) {
        compose_banner.append_compose_banner_to_banner_list(
            $(stream_wildcard_html),
            opts.$banner_container,
        );
    } else {
        // if there is already a banner, replace it with the new one
        compose_banner.update_or_append_banner(
            $(stream_wildcard_html),
            classname,
            opts.$banner_container,
        );
    }

    user_acknowledged_stream_wildcard = false;
}

export function clear_stream_wildcard_warnings($banner_container: JQuery): void {
    const classname = compose_banner.CLASSNAMES.wildcard_warning;
    $banner_container.find(`.${CSS.escape(classname)}`).remove();
}

export function set_user_acknowledged_stream_wildcard_flag(value: boolean): void {
    user_acknowledged_stream_wildcard = value;
}

function is_recipient_large_stream(): boolean {
    const stream_id = compose_state.stream_id();
    if (stream_id === undefined) {
        return false;
    }
    return peer_data.get_subscriber_count(stream_id) > wildcard_mention_threshold;
}

export function topic_participant_count_more_than_threshold(
    stream_id: number,
    topic: string,
): boolean {
    // Topic participants:
    // Users who either sent or reacted to the messages in the topic.
    const participant_ids = new Set();

    const sender_ids = recent_senders.get_topic_recent_senders(stream_id, topic);
    for (const id of sender_ids) {
        participant_ids.add(id);
    }

    // If senders count is greater than threshold, no need to calculate reactors.
    if (participant_ids.size > wildcard_mention_threshold) {
        return true;
    }

    for (const sender_id of sender_ids) {
        const message_ids = recent_senders.get_topic_message_ids_for_sender(
            stream_id,
            topic,
            sender_id,
        );
        for (const message_id of message_ids) {
            const message = message_store.get(message_id);
            if (message) {
                const message_reactions = reactions.get_message_reactions(message);
                const reactor_ids = message_reactions.flatMap((obj) => obj.user_ids);
                for (const id of reactor_ids) {
                    participant_ids.add(id);
                }
                if (participant_ids.size > wildcard_mention_threshold) {
                    return true;
                }
            }
        }
    }

    return false;
}

function is_recipient_large_topic(): boolean {
    const stream_id = compose_state.stream_id();
    if (stream_id === undefined) {
        return false;
    }
    return topic_participant_count_more_than_threshold(stream_id, compose_state.topic());
}

function user_can_mention_many_users(): boolean {
    return settings_data.user_has_permission_for_group_setting(
        realm.realm_can_mention_many_users_group,
        "can_mention_many_users_group",
        "realm",
    );
}

export function stream_wildcard_mention_allowed(): boolean {
    return !is_recipient_large_stream() || user_can_mention_many_users();
}

export function topic_wildcard_mention_allowed(): boolean {
    return !is_recipient_large_topic() || user_can_mention_many_users();
}

export function set_wildcard_mention_threshold(value: number): void {
    wildcard_mention_threshold = value;
}

export function validate_stream_message_mentions(opts: StreamWildcardOptions): boolean {
    const subscriber_count = peer_data.get_subscriber_count(opts.stream_id) || 0;

    // If the user is attempting to do a wildcard mention in a large
    // stream, check if they permission to do so. If yes, warn them
    // if they haven't acknowledged the wildcard warning yet.
    if (opts.stream_wildcard_mention !== null && subscriber_count > wildcard_mention_threshold) {
        if (!user_can_mention_many_users()) {
            const new_row_html = render_wildcard_mention_not_allowed_error({
                banner_type: compose_banner.ERROR,
                classname: compose_banner.CLASSNAMES.wildcards_not_allowed,
                wildcard_mention_string: opts.stream_wildcard_mention,
            });
            compose_banner.append_compose_banner_to_banner_list(
                $(new_row_html),
                opts.$banner_container,
            );
            if (is_validating_compose_box) {
                disabled_send_tooltip_message_html = WILDCARD_MENTION_ERROR_TOOLTIP_MESSAGE;
            }
            return false;
        }

        if (!user_acknowledged_stream_wildcard) {
            show_stream_wildcard_warnings(opts);
            compose_ui.hide_compose_spinner();
            if (is_validating_compose_box) {
                disabled_send_tooltip_message_html =
                    CHANNEL_WILDCARD_ACKNOWLEDGE_MISSING_ERROR_TOOLTIP_MESSAGE;
            }
            return false;
        }
    } else {
        // the message no longer contains @all or @everyone
        clear_stream_wildcard_warnings(opts.$banner_container);
    }
    // at this point, the user has either acknowledged the warning or removed @all / @everyone
    user_acknowledged_stream_wildcard = false;

    return true;
}

export function validate_stream_message_address_info(sub: StreamSubscription): boolean {
    if (sub.is_archived) {
        compose_banner.show_stream_does_not_exist_error(sub.name);
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = INVALID_CHANNEL_ERROR_TOOLTIP_MESSAGE;
        }
        return false;
    }
    if (sub.subscribed) {
        return true;
    }
    compose_banner.show_stream_not_subscribed_error(sub, UNSUBSCRIBED_CHANNEL_ERROR_MESSAGE);
    if (is_validating_compose_box) {
        disabled_send_tooltip_message_html = UNSUBSCRIBED_CHANNEL_ERROR_MESSAGE;
    }
    return false;
}

function validate_stream_message(scheduling_message: boolean, show_banner = true): boolean {
    const $banner_container = $("#compose_banners");
    const stream_id = compose_state.stream_id();
    const no_channel_selected = stream_id === undefined;
    if (no_channel_selected) {
        report_validation_error(
            NO_CHANNEL_SELECTED_ERROR_MESSAGE,
            compose_banner.CLASSNAMES.missing_stream,
            $banner_container,
            $("#compose_select_recipient_widget_wrapper"),
            show_banner,
        );
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = NO_CHANNEL_SELECTED_ERROR_MESSAGE;
        }
        return false;
    }

    if (!stream_data.can_use_empty_topic(compose_state.stream_id())) {
        const topic = compose_state.topic();
        const missing_topic = util.is_topic_name_considered_empty(topic);
        if (missing_topic) {
            if (show_banner) {
                compose_banner.topic_missing_error(util.get_final_topic_display_name(""));
            }
            if (is_validating_compose_box) {
                disabled_send_tooltip_message_html = get_topics_required_error_message_html();
            }
            return false;
        }
    }

    const sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        compose_banner.show_stream_does_not_exist_error(stream_id.toString());
        if (is_validating_compose_box) {
            // show_stream_does_not_exist_error already opens the channel selection dropdown.
            disabled_send_tooltip_message_html = INVALID_CHANNEL_ERROR_TOOLTIP_MESSAGE;
        }
        return false;
    }

    if (!stream_data.can_post_messages_in_stream(sub)) {
        compose_banner.show_error_message(
            NO_PERMISSION_TO_POST_IN_CHANNEL_ERROR_MESSAGE,
            compose_banner.CLASSNAMES.no_post_permissions,
            $banner_container,
        );

        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = NO_PERMISSION_TO_POST_IN_CHANNEL_ERROR_MESSAGE;
            posting_policy_error_message = NO_PERMISSION_TO_POST_IN_CHANNEL_ERROR_MESSAGE;
        }
        return false;
    }

    const stream_wildcard_mention = util.find_stream_wildcard_mentions(
        compose_state.message_content(),
    );

    if (
        !validate_stream_message_address_info(sub) ||
        !validate_stream_message_mentions({
            stream_id: sub.stream_id,
            $banner_container,
            stream_wildcard_mention,
            scheduling_message,
        })
    ) {
        return false;
    }

    return true;
}

// The function checks whether the recipients are users of the realm or cross realm users (bots
// for now)
function validate_private_message(show_banner = true): boolean {
    const user_ids = compose_pm_pill.get_user_ids();
    const user_ids_string = util.sorted_ids(user_ids).join(",");
    const $banner_container = $("#compose_banners");
    const missing_direct_message_recipient = user_ids.length === 0;

    if (missing_direct_message_recipient) {
        report_validation_error(
            NO_PRIVATE_RECIPIENT_ERROR_MESSAGE,
            compose_banner.CLASSNAMES.missing_private_message_recipient,
            $banner_container,
            $("#private_message_recipient"),
            show_banner,
        );
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = NO_PRIVATE_RECIPIENT_ERROR_MESSAGE;
        }
        return false;
    } else if (realm.realm_is_zephyr_mirror_realm) {
        // For Zephyr mirroring realms, the frontend doesn't know which users exist
        return true;
    }

    const direct_message_error_string = check_dm_permissions_and_get_error_string(user_ids_string);
    if (direct_message_error_string) {
        compose_banner.cannot_send_direct_message_error(direct_message_error_string);
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = direct_message_error_string;
            posting_policy_error_message = direct_message_error_string;
        }
        return false;
    }

    let context = {};

    for (const user_id of user_ids) {
        if (!people.is_person_active(user_id)) {
            context = {full_name: people.get_by_user_id(user_id).full_name};
            const error_message = $t(
                {defaultMessage: "You cannot send messages to deactivated users."},
                context,
            );
            compose_banner.show_error_message(
                error_message,
                compose_banner.CLASSNAMES.deactivated_user,
                $banner_container,
                $("#private_message_recipient"),
            );

            if (is_validating_compose_box) {
                disabled_send_tooltip_message_html = error_message;
            }
            return false;
        }
    }

    return true;
}

export function check_overflow_text($container: JQuery): number {
    // This function is called when typing every character in the
    // compose box, so it's important that it not doing anything
    // expensive.
    const $textarea = $container.find<HTMLTextAreaElement>(".message-textarea");
    // Match the behavior of compose_state.message_content of trimming trailing whitespace
    const text = $textarea.val()!.trimEnd();
    const max_length = realm.max_message_length;
    const remaining_characters = max_length - text.length;
    const $indicator = $container.find(".message-limit-indicator");
    const is_edit_container = $textarea.closest(".message_row").length > 0;

    const old_no_message_content = no_message_content;
    const old_message_too_long = message_too_long;

    if (text.length > max_length) {
        $indicator.removeClass("textarea-approaching-limit");
        $textarea.removeClass("textarea-approaching-limit");
        $indicator.addClass("textarea-over-limit");
        $textarea.addClass("textarea-over-limit");
        $indicator.html(
            render_compose_limit_indicator({
                remaining_characters,
            }),
        );
        if (is_edit_container) {
            set_message_too_long_for_edit(true, $container);
        } else {
            set_message_too_long_for_compose(true);
        }
    } else if (remaining_characters <= 900) {
        $indicator.removeClass("textarea-over-limit");
        $textarea.removeClass("textarea-over-limit");
        $indicator.addClass("textarea-approaching-limit");
        $textarea.addClass("textarea-approaching-limit");
        $indicator.html(
            render_compose_limit_indicator({
                remaining_characters,
            }),
        );
        if (is_edit_container) {
            set_message_too_long_for_edit(false, $container);
        } else {
            set_message_too_long_for_compose(false);
        }
    } else {
        $indicator.text("");
        $textarea.removeClass("textarea-over-limit");
        $textarea.removeClass("textarea-approaching-limit");

        if (is_edit_container) {
            set_message_too_long_for_edit(false, $container);
        } else {
            set_message_too_long_for_compose(false);
        }
    }

    if (!is_edit_container) {
        // Update the state for whether the message is empty.
        set_no_message_content(text.length === 0);
        if (
            message_too_long !== old_message_too_long ||
            old_no_message_content !== no_message_content
        ) {
            // If this keystroke changed the truth status for whether
            // the message is empty or too long, then we need to
            // refresh the send button status from scratch. This is
            // expensive, but naturally debounced by the fact this
            // changes rarely.
            validate_and_update_send_button_status();
        }
    }
    return text.length;
}

export let validate_and_update_send_button_status = function (): void {
    const is_valid = validate(false, false);
    const $send_button = $("#compose-send-button");
    $send_button.toggleClass("disabled-message-send-controls", !is_valid);
    const send_button_element: ReferenceElement = util.the($send_button);
    if (send_button_element._tippy?.state.isVisible) {
        // If the tooltip is displayed, we update tooltip content
        // and other properties by hiding and showing the tooltip again.
        send_button_element._tippy.hide();
        send_button_element._tippy.show();
    }
};

export function rewire_validate_and_update_send_button_status(
    value: typeof validate_and_update_send_button_status,
): void {
    validate_and_update_send_button_status = value;
}
export function validate_message_length($container: JQuery, trigger_flash = true): boolean {
    const $textarea = $container.find<HTMLTextAreaElement>(".message-textarea");
    // Match the behavior of compose_state.message_content of trimming trailing whitespace
    const text = $textarea.val()!.trimEnd();

    const message_too_long_for_compose = text.length > realm.max_message_length;
    // Usually, check_overflow_text maintains this, but since we just
    // did the check, make sure it's up to date.
    set_message_too_long_for_compose(message_too_long_for_compose);

    if (message_too_long_for_compose) {
        if (trigger_flash) {
            $textarea.addClass("flash");
            // This must be synchronized with the `flash` CSS.
            setTimeout(() => $textarea.removeClass("flash"), 500);
        }
        return false;
    }
    return true;
}

function report_validation_error(
    message: string,
    classname: string,
    $container: JQuery,
    $bad_input: JQuery,
    show_banner: boolean,
    precursor?: () => void,
): void {
    if (show_banner) {
        if (precursor) {
            precursor();
        }
        compose_banner.show_error_message(message, classname, $container, $bad_input);
    }
}

export let validate = (scheduling_message: boolean, show_banner = true): boolean => {
    is_validating_compose_box = true;
    posting_policy_error_message = "";
    disabled_send_tooltip_message_html = "";
    const message_content = compose_state.message_content();
    // The validation checks in this function are in a specific priority order. Don't
    // change their order unless you want to change which priority they're shown in.

    if (
        compose_state.get_message_type() !== "private" &&
        !validate_stream_message(scheduling_message, show_banner)
    ) {
        blueslip.debug("Invalid compose state: Stream message validation failed");
        is_validating_compose_box = false;
        return false;
    }

    if (compose_state.get_message_type() === "private" && !validate_private_message(show_banner)) {
        blueslip.debug("Invalid compose state: Private message validation failed");
        is_validating_compose_box = false;
        return false;
    }

    const no_message_content = /^\s*$/.test(message_content);
    set_no_message_content(no_message_content);
    if (no_message_content) {
        if (show_banner) {
            // If you tried actually sending a message with empty
            // compose, flash the textarea as invalid.
            $("textarea#compose-textarea").toggleClass("invalid", true);
            $("textarea#compose-textarea").trigger("focus");
        }
        blueslip.debug("Invalid compose state: Empty message");
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = NO_MESSAGE_CONTENT_ERROR_MESSAGE;
        }
        is_validating_compose_box = false;
        return false;
    } else if ($("textarea#compose-textarea").hasClass("invalid")) {
        // Hide the invalid indicator now that it's non-empty.
        $("textarea#compose-textarea").toggleClass("invalid", false);
    }

    if ($("#zephyr-mirror-error").hasClass("show")) {
        const error_message = $t({
            defaultMessage: "You need to be running Zephyr mirroring in order to send messages!",
        });
        compose_banner.show_error_message(
            error_message,
            compose_banner.CLASSNAMES.zephyr_not_running,
            $("#compose_banners"),
        );
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = error_message;
        }
        blueslip.debug("Invalid compose state: Zephyr mirroring not running");
        is_validating_compose_box = false;
        return false;
    }
    // TODO: This doesn't actually show a banner, it triggers a flash
    const trigger_flash = show_banner;
    if (!validate_message_length($("#send_message_form"), trigger_flash)) {
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = get_message_too_long_for_compose_error();
        }
        blueslip.debug("Invalid compose state: Message too long");
        is_validating_compose_box = false;
        return false;
    }

    if (upload_in_progress) {
        if (is_validating_compose_box) {
            disabled_send_tooltip_message_html = UPLOAD_IN_PROGRESS_ERROR_TOOLTIP_MESSAGE;
        }
        blueslip.debug("Invalid compose state: Upload in progress");
        is_validating_compose_box = false;
        return false;
    }

    is_validating_compose_box = false;
    return true;
};

export function rewire_validate(value: typeof validate): void {
    validate = value;
}

export function convert_mentions_to_silent_in_direct_messages(
    mention_text: string,
    full_name: string,
    user_id: number,
): string {
    if (compose_state.get_message_type() !== "private") {
        return mention_text;
    }

    const recipient_user_id = compose_pm_pill.get_user_ids();
    if (recipient_user_id.toString() !== user_id.toString()) {
        return mention_text;
    }

    const user = people.get_user_by_id_assert_valid(user_id);
    if (user.is_bot) {
        // Since bots often process mentions as requests for them to
        // do things, prefer non-silent mentions when DMing them.
        return mention_text;
    }

    const silent_mention_text = people.get_mention_syntax(full_name, user_id, true);
    return silent_mention_text;
}

export function initialize(): void {
    $("body").on(
        "click",
        ".view_user_group_mention",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.preventDefault();
            e.stopPropagation();
            toggle_user_group_info_popover(this, undefined);
        },
    );
}
