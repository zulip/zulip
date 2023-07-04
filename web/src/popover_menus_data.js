/* This module provides relevant data to render popovers that require multiple args.
   This helps keep the popovers code small and keep it focused on rendering side of things. */

import ClipboardJS from "clipboard";
import {parseISO} from "date-fns";
import $ from "jquery";
import tippy from "tippy.js";

import * as resolved_topic from "../shared/src/resolved_topic";

import * as buddy_data from "./buddy_data";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_edit from "./message_edit";
import * as message_lists from "./message_lists";
import * as muted_users from "./muted_users";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as starred_messages from "./starred_messages";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as user_profile from "./user_profile";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_topics from "./user_topics";

export function get_actions_popover_content_context(message_id) {
    const message = message_lists.current.get(message_id);
    const message_container = message_lists.current.view.message_containers.get(message.id);
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
        view_source_menu_item = $t({defaultMessage: "View message source"});
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

    // Disabling this for /me messages is a temporary workaround
    // for the fact that we don't have a styling for how that
    // should look.  See also condense.js.
    const should_display_collapse =
        !message.locally_echoed && !message.is_me_message && !message.collapsed && not_spectator;
    const should_display_uncollapse =
        !message.locally_echoed && !message.is_me_message && message.collapsed;

    const should_display_quote_and_reply = message.content !== "<p>(deleted)</p>" && not_spectator;

    const conversation_time_url = hash_util.by_conversation_and_time_url(message);

    const should_display_delete_option = message_edit.get_deletability(message) && not_spectator;
    const should_display_read_receipts_option =
        page_params.realm_enable_read_receipts && not_spectator;

    function is_add_reaction_icon_visible() {
        const $message_row = message_lists.current.get_row(message_id);
        return $message_row.find(".message_controls .reaction_button").is(":visible");
    }

    // Since we only display msg actions and star icons on windows smaller than
    // `media_breakpoints.sm_min`, we need to include the reaction button in the
    // popover if it is not displayed.
    const should_display_add_reaction_option =
        !message.is_me_message && !is_add_reaction_icon_visible() && not_spectator;

    return {
        message_id: message.id,
        stream_id: message.stream_id,
        editability_menu_item,
        move_message_menu_item,
        should_display_mark_as_unread,
        view_source_menu_item,
        should_display_collapse,
        should_display_uncollapse,
        should_display_add_reaction_option,
        should_display_hide_option,
        conversation_time_url,
        narrowed: narrow_state.active(),
        should_display_delete_option,
        should_display_read_receipts_option,
        should_display_quote_and_reply,
    };
}

export function get_topic_popover_content_context({stream_id, topic_name, url}) {
    const sub = sub_store.get(stream_id);
    const topic_muted = user_topics.is_topic_muted(sub.stream_id, topic_name);
    const topic_unmuted = user_topics.is_topic_unmuted(sub.stream_id, topic_name);
    const has_starred_messages = starred_messages.get_count_in_topic(sub.stream_id, topic_name) > 0;
    const can_move_topic = settings_data.user_can_move_messages_between_streams();
    const can_rename_topic = settings_data.user_can_move_messages_to_another_topic();
    const visibility_policy = user_topics.get_topic_visibility_policy(sub.stream_id, topic_name);
    const all_visibility_policies = user_topics.all_visibility_policies;
    return {
        stream_name: sub.name,
        stream_id: sub.stream_id,
        stream_muted: sub.is_muted,
        topic_name,
        topic_muted,
        topic_unmuted,
        can_move_topic,
        can_rename_topic,
        is_realm_admin: page_params.is_admin,
        topic_is_resolved: resolved_topic.is_resolved(topic_name),
        color: sub.color,
        has_starred_messages,
        url,
        visibility_policy,
        all_visibility_policies,
        development: page_params.development_environment,
    };
}

export function get_change_visibility_policy_popover_content_context(stream_id, topic_name) {
    const visibility_policy = user_topics.get_topic_visibility_policy(stream_id, topic_name);
    const sub = sub_store.get(stream_id);
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

export function clipboard_enable(arg) {
    // arg is a selector or element
    // We extract this function for testing purpose.
    if (arg) {
        return new ClipboardJS(arg);
    }
    return null;
}

function copy_email_handler(e) {
    const $email_el = $(e.trigger.parentElement);
    const $copy_icon = $email_el.find("i");

    // only change the parent element's text back to email
    // and not overwrite the tooltip.
    const email_textnode = $email_el[0].childNodes[2];

    $email_el.addClass("email_copied");
    email_textnode.nodeValue = $t({defaultMessage: "Email copied"});

    setTimeout(() => {
        $email_el.removeClass("email_copied");
        email_textnode.nodeValue = $copy_icon.attr("data-clipboard-text");
    }, 1500);
    e.clearSelection();
}

export function init_email_clipboard() {
    /*
        This shows (and enables) the copy-text icon for folks
        who have names that would overflow past the right
        edge of our user mention popup.
    */
    $(".user_popover_email").each(function () {
        if (this.clientWidth < this.scrollWidth) {
            const $email_el = $(this);
            const $copy_email_icon = $email_el.find("i");

            /*
                For deactivated users, the copy-email icon will
                not even be present in the HTML, so we don't do
                anything.  We don't reveal emails for deactivated
                users.
            */
            if ($copy_email_icon[0]) {
                $copy_email_icon.removeClass("hide_copy_icon");
                const copy_email_clipboard = clipboard_enable($copy_email_icon[0]);
                copy_email_clipboard.on("success", copy_email_handler);
            }
        }
    });
}

export function init_email_tooltip(user) {
    /*
        This displays the email tooltip for folks
        who have names that would overflow past the right
        edge of our user mention popup.
    */

    $(".user_popover_email").each(function () {
        if (this.clientWidth < this.scrollWidth) {
            tippy(this, {
                placement: "bottom",
                content: people.get_visible_email(user),
                interactive: true,
            });
        }
    });
}

export function load_medium_avatar(user, $elt) {
    const user_avatar_url = people.medium_avatar_url_for_person(user);
    const sender_avatar_medium = new Image();

    sender_avatar_medium.src = user_avatar_url;
    $(sender_avatar_medium).on("load", function () {
        $elt.css("background-image", "url(" + $(this).attr("src") + ")");
    });
}

export function render_user_info_popover(
    user,
    is_sender_popover,
    has_message_context,
    template_class,
) {
    const is_me = people.is_my_user_id(user.user_id);

    let invisible_mode = false;

    if (is_me) {
        invisible_mode = !user_settings.presence_enabled;
    }

    const muting_allowed = !is_me && !user.is_bot;
    const is_active = people.is_active_user_for_popover(user.user_id);
    const is_system_bot = user.is_system_bot;
    const status_text = user_status.get_status_text(user.user_id);
    const status_emoji_info = user_status.get_status_emoji(user.user_id);
    const spectator_view = page_params.is_spectator;

    // TODO: The show_manage_menu calculation can get a lot simpler
    // if/when we allow muting bot users.
    const can_manage_user = page_params.is_admin && !is_me && !is_system_bot;
    const show_manage_menu = !spectator_view && (muting_allowed || can_manage_user);

    let date_joined;
    if (spectator_view) {
        date_joined = timerender.get_localized_date_or_time_for_format(
            parseISO(user.date_joined),
            "dayofyear_year",
        );
    }
    // Filtering out only those profile fields that can be display in the popover and are not empty.
    const field_types = page_params.custom_profile_field_types;
    const display_profile_fields = page_params.custom_profile_fields
        .map((f) => user_profile.get_custom_profile_field_data(user, f, field_types))
        .filter((f) => f.display_in_profile_summary && f.value !== undefined && f.value !== null);

    const args = {
        class: template_class,
        user_is_guest: user.is_guest,
        user_avatar: people.small_avatar_url_for_person(user),
        invisible_mode,
        can_send_private_message:
            is_active &&
            !is_me &&
            page_params.realm_private_message_policy !==
                settings_config.private_message_policy_values.disabled.code,
        display_profile_fields,
        has_message_context,
        is_active,
        is_bot: user.is_bot,
        is_me,
        is_sender_popover,
        pm_with_url: hash_util.pm_with_url(user.email),
        user_circle_class: buddy_data.get_user_circle_class(user.user_id),
        private_message_class: "compose_private_message",
        sent_by_uri: hash_util.by_sender_url(user.email),
        show_manage_menu,
        user_email: user.delivery_email,
        user_full_name: user.full_name,
        user_id: user.user_id,
        user_last_seen_time_status: buddy_data.user_last_seen_time_status(user.user_id),
        user_time: people.get_user_time(user.user_id),
        user_type: people.get_user_type(user.user_id),
        status_content_available: Boolean(status_text || status_emoji_info),
        status_text,
        status_emoji_info,
        user_mention_syntax: people.get_mention_syntax(user.full_name, user.user_id),
        date_joined,
        spectator_view,
    };

    if (user.is_bot) {
        const bot_owner_id = user.bot_owner_id;
        if (is_system_bot) {
            args.is_system_bot = is_system_bot;
        } else if (bot_owner_id) {
            const bot_owner = people.get_by_user_id(bot_owner_id);
            args.bot_owner = bot_owner;
        }
    }

    // Note: We pass the normal-size avatar in initial rendering, and
    // then query the server to replace it with the medium-size
    // avatar.  The purpose of this double-fetch approach is to take
    // advantage of the fact that the browser should already have the
    // low-resolution image cached and thus display a low-resolution
    // avatar rather than a blank area during the network delay for
    // fetching the medium-size one.
    return args;
}
