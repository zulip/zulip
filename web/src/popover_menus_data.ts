/* This module provides relevant data to render popovers that require multiple args.
   This helps keep the popovers code small and keep it focused on rendering side of things. */

import assert from "minimalistic-assert";

import * as resolved_topic from "../shared/src/resolved_topic.ts";

import * as buddy_data from "./buddy_data.ts";
import * as gear_menu_util from "./gear_menu_util.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_edit from "./message_edit.ts";
import * as message_lists from "./message_lists.ts";
import * as muted_users from "./muted_users.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as settings_config from "./settings_config.ts";
import type {ColorSchemeValues} from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as starred_messages from "./starred_messages.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import {num_unread_for_topic} from "./unread.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import type {UserStatusEmojiInfo} from "./user_status.ts";
import * as user_topics from "./user_topics.ts";
import type {AllVisibilityPolicies} from "./user_topics.ts";
import * as util from "./util.ts";

type ActionPopoverContext = {
    message_id: number;
    stream_id: number | undefined;
    editability_menu_item: string | undefined;
    move_message_menu_item: string | undefined;
    view_source_menu_item: string | undefined;
    should_display_hide_option: boolean;
    should_display_mark_as_unread: boolean;
    should_display_collapse: boolean;
    should_display_uncollapse: boolean;
    should_display_quote_message: boolean;
    conversation_time_url: string;
    should_display_delete_option: boolean;
    should_display_read_receipts_option: boolean;
    should_display_add_reaction_option: boolean;
};

type TopicPopoverContext = {
    stream_name: string;
    stream_id: number;
    stream_muted: boolean;
    topic_display_name: string;
    is_empty_string_topic: boolean;
    topic_unmuted: boolean;
    is_spectator: boolean;
    is_topic_empty: boolean;
    can_move_topic: boolean;
    can_rename_topic: boolean;
    is_realm_admin: boolean;
    topic_is_resolved: boolean;
    has_starred_messages: boolean;
    has_unread_messages: boolean;
    url: string;
    visibility_policy: number | false;
    all_visibility_policies: AllVisibilityPolicies;
};

type VisibilityChangePopoverContext = {
    stream_id: number;
    topic_name: string;
    visibility_policy: number | false;
    stream_muted: boolean;
    topic_unmuted: boolean;
    all_visibility_policies: AllVisibilityPolicies;
};

type PersonalMenuContext = {
    user_id: number;
    invisible_mode: boolean;
    user_is_guest: boolean;
    spectator_view: boolean;
    user_avatar?: string | undefined | null;
    is_active: boolean;
    user_circle_class: string;
    user_last_seen_time_status: string;
    user_full_name: string;
    user_type: string | undefined;
    status_content_available: boolean;
    show_placeholder_for_status_text: boolean;
    status_text: string | undefined;
    status_emoji_info: UserStatusEmojiInfo | undefined;
    user_color_scheme: number;
    color_scheme_values: ColorSchemeValues;
};

type GearMenuContext = {
    realm_name: string;
    realm_url: string;
    is_owner: boolean;
    is_admin: boolean;
    is_spectator: boolean;
    is_self_hosted: boolean;
    is_development_environment: boolean;
    is_plan_limited: boolean;
    is_plan_standard: boolean;
    is_plan_standard_sponsored_for_free: boolean;
    is_plan_plus: boolean;
    is_org_on_paid_plan: boolean;
    is_business_org: boolean;
    is_education_org: boolean;
    standard_plan_name: string;
    server_needs_upgrade: boolean;
    version_display_string: string;
    apps_page_url: string;
    can_create_multiuse_invite: boolean;
    can_invite_users_by_email: boolean;
    is_guest: boolean;
    login_link: string;
    promote_sponsoring_zulip: boolean;
    show_billing: boolean;
    show_remote_billing: boolean;
    show_plans: boolean;
    show_webathena: boolean;
    sponsorship_pending: boolean;
    user_has_billing_access: boolean;
    user_color_scheme: number;
    color_scheme_values: ColorSchemeValues;
};

export function get_actions_popover_content_context(message_id: number): ActionPopoverContext {
    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(message_id);
    assert(message !== undefined);
    const message_container = message_lists.current.view.message_containers.get(message.id)!;
    const not_spectator = !page_params.is_spectator;
    const should_display_hide_option =
        muted_users.is_user_muted(message.sender_id) &&
        !message_container.is_hidden &&
        not_spectator;
    const is_content_editable = message_edit.is_content_editable(message);
    const can_move_message = message_edit.can_move_message(message);

    let editability_menu_item;
    let move_message_menu_item;
    let view_source_menu_item;

    if (is_content_editable) {
        editability_menu_item = $t({defaultMessage: "Edit message"});
    } else {
        view_source_menu_item = $t({defaultMessage: "View original message"});
    }

    if (can_move_message) {
        move_message_menu_item = $t({defaultMessage: "Move messages"});
    }

    // We do not offer "Mark as unread" on messages in streams
    // that the user is not currently subscribed to. Zulip has an
    // invariant that all unread messages must be in streams the
    // user is subscribed to, and so the server will ignore any
    // messages in such streams; it's better to hint this is not
    // useful by not offering the option.
    //
    // We also require that the message is currently marked as
    // read. Theoretically, it could be useful to offer this even
    // for a message that is already unread, so you can mark those
    // below it as unread; but that's an unlikely situation, and
    // showing it can be a confusing source of clutter. We may
    // want to revise this algorithm specifically in the context
    // of interleaved views.
    //
    // To work around #22893, we also only offer the option if the
    // fetch_status data structure means we'll be able to mark
    // everything below the current message as read correctly.
    const not_stream_message = message.type !== "stream";
    const subscribed_to_stream =
        message.type === "stream" && stream_data.is_subscribed(message.stream_id);
    const should_display_mark_as_unread =
        !message.unread && not_spectator && (not_stream_message || subscribed_to_stream);

    let stream_id;
    if (!not_stream_message) {
        stream_id = message.stream_id;
    }

    // Disabling this for /me messages is a temporary workaround
    // for the fact that we don't have a styling for how that
    // should look.  See also condense.js.
    const should_display_collapse =
        !message.locally_echoed && !message.is_me_message && !message.collapsed && not_spectator;
    const should_display_uncollapse =
        !message.locally_echoed && !message.is_me_message && message.collapsed;

    const should_display_quote_message = not_spectator;

    const conversation_time_url = hash_util.by_conversation_and_time_url(message);

    const should_display_delete_option = message_edit.get_deletability(message) && not_spectator;
    const should_display_read_receipts_option = realm.realm_enable_read_receipts && not_spectator;

    function is_add_reaction_icon_visible(): boolean {
        assert(message_lists.current !== undefined);
        const $message_row = message_lists.current.get_row(message_id);
        return $message_row.find(".message_controls .reaction_button").is(":visible");
    }

    // Since we only display msg actions and star icons on windows smaller than
    // `media_breakpoints.sm_min`, we need to include the reaction button in the
    // popover if it is not displayed.
    const should_display_add_reaction_option =
        !message.is_me_message &&
        !is_add_reaction_icon_visible() &&
        not_spectator &&
        !(stream_id && stream_data.is_stream_archived(stream_id));

    return {
        message_id: message.id,
        stream_id,
        editability_menu_item,
        move_message_menu_item,
        should_display_mark_as_unread,
        view_source_menu_item,
        should_display_collapse,
        should_display_uncollapse,
        should_display_add_reaction_option,
        should_display_hide_option,
        conversation_time_url,
        should_display_delete_option,
        should_display_read_receipts_option,
        should_display_quote_message,
    };
}

export function get_topic_popover_content_context({
    stream_id,
    topic_name,
    url,
}: {
    stream_id: number;
    topic_name: string;
    url: string;
}): TopicPopoverContext {
    const sub = sub_store.get(stream_id);
    assert(sub !== undefined);
    const topic_unmuted = user_topics.is_topic_unmuted(sub.stream_id, topic_name);
    const has_starred_messages = starred_messages.get_count_in_topic(sub.stream_id, topic_name) > 0;
    const has_unread_messages = num_unread_for_topic(sub.stream_id, topic_name) > 0;
    const can_move_topic = settings_data.user_can_move_messages_between_streams();
    const can_rename_topic = settings_data.user_can_move_messages_to_another_topic();
    const visibility_policy = user_topics.get_topic_visibility_policy(sub.stream_id, topic_name);
    const all_visibility_policies = user_topics.all_visibility_policies;
    const is_spectator = page_params.is_spectator;
    const is_topic_empty = is_topic_definitely_empty(stream_id, topic_name);
    return {
        stream_name: sub.name,
        stream_id: sub.stream_id,
        stream_muted: sub.is_muted,
        topic_display_name: util.get_final_topic_display_name(topic_name),
        is_empty_string_topic: topic_name === "",
        topic_unmuted,
        is_spectator,
        is_topic_empty,
        can_move_topic,
        can_rename_topic,
        is_realm_admin: current_user.is_admin,
        topic_is_resolved: resolved_topic.is_resolved(topic_name),
        has_starred_messages,
        has_unread_messages,
        url,
        visibility_policy,
        all_visibility_policies,
    };
}

export function get_change_visibility_policy_popover_content_context(
    stream_id: number,
    topic_name: string,
): VisibilityChangePopoverContext {
    const visibility_policy = user_topics.get_topic_visibility_policy(stream_id, topic_name);
    const sub = sub_store.get(stream_id);
    assert(sub !== undefined);
    const all_visibility_policies = user_topics.all_visibility_policies;
    const topic_unmuted = visibility_policy === all_visibility_policies.UNMUTED;
    return {
        stream_id,
        topic_name,
        visibility_policy,
        stream_muted: sub.is_muted,
        topic_unmuted,
        all_visibility_policies,
    };
}

export function get_personal_menu_content_context(): PersonalMenuContext {
    const my_user_id = current_user.user_id;
    const invisible_mode = !user_settings.presence_enabled;
    const status_text = user_status.get_status_text(my_user_id);
    const status_emoji_info = user_status.get_status_emoji(my_user_id);
    return {
        user_id: my_user_id,
        invisible_mode,
        user_is_guest: current_user.is_guest,
        spectator_view: page_params.is_spectator,

        // user information
        user_avatar: current_user.avatar_url_medium,
        is_active: people.is_active_user_for_popover(my_user_id),
        user_circle_class: buddy_data.get_user_circle_class(my_user_id),
        user_last_seen_time_status: buddy_data.user_last_seen_time_status(my_user_id),
        user_full_name: current_user.full_name,
        user_type: people.get_user_type(my_user_id),

        // user status
        status_content_available: Boolean(status_text ?? status_emoji_info),
        show_placeholder_for_status_text: !status_text && status_emoji_info !== undefined,
        status_text,
        status_emoji_info,

        // user color scheme
        user_color_scheme: user_settings.color_scheme,
        color_scheme_values: settings_config.color_scheme_values,
    };
}

export function get_gear_menu_content_context(): GearMenuContext {
    const user_has_billing_access = current_user.is_billing_admin || current_user.is_owner;
    const is_plan_standard = realm.realm_plan_type === 3;
    const is_plan_plus = realm.realm_plan_type === 10;
    const is_org_on_paid_plan = is_plan_standard || is_plan_plus;
    return {
        realm_name: realm.realm_name,
        realm_url: new URL(realm.realm_url).hostname,
        is_owner: current_user.is_owner,
        is_admin: current_user.is_admin,
        is_spectator: page_params.is_spectator,
        is_self_hosted: realm.realm_plan_type === 1,
        is_development_environment: page_params.development_environment,
        is_plan_limited: realm.realm_plan_type === 2,
        is_plan_standard,
        is_plan_standard_sponsored_for_free: realm.realm_plan_type === 4,
        is_plan_plus,
        is_org_on_paid_plan,
        is_business_org: realm.realm_org_type === 10,
        is_education_org: realm.realm_org_type === 30 || realm.realm_org_type === 35,
        standard_plan_name: "Zulip Cloud Standard",
        server_needs_upgrade: realm.server_needs_upgrade,
        version_display_string: gear_menu_util.version_display_string(),
        apps_page_url: page_params.apps_page_url,
        can_create_multiuse_invite: settings_data.user_can_create_multiuse_invite(),
        can_invite_users_by_email: settings_data.user_can_invite_users_by_email(),
        is_guest: current_user.is_guest,
        login_link: page_params.development_environment ? "/devlogin/" : "/login/",
        promote_sponsoring_zulip: page_params.promote_sponsoring_zulip,
        show_billing: page_params.show_billing,
        show_remote_billing: page_params.show_remote_billing,
        show_plans: page_params.show_plans,
        show_webathena: page_params.show_webathena,
        sponsorship_pending: page_params.sponsorship_pending,
        user_has_billing_access,
        // user color scheme
        user_color_scheme: user_settings.color_scheme,
        color_scheme_values: settings_config.color_scheme_values,
    };
}

function is_topic_definitely_empty(stream_id: number, topic: string): boolean {
    const current_narrow_stream_id = narrow_state.stream_id();
    const current_narrow_topic = narrow_state.topic();

    if (
        current_narrow_stream_id === undefined ||
        current_narrow_topic === undefined ||
        current_narrow_stream_id !== stream_id ||
        current_narrow_topic !== topic
    ) {
        return false;
    }

    const is_current_message_list_empty = message_lists.current?.data.empty();
    if (!is_current_message_list_empty) {
        return false;
    }

    const is_oldest_message_found = message_lists.current?.data.fetch_status.has_found_oldest();
    if (!is_oldest_message_found) {
        return false;
    }

    return true;
}
