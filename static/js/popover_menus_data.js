/* This module provides relevant data to render popovers that require multiple args.
   This helps keep the popovers code small and keep it focused on rendering side of things. */

import * as feature_flags from "./feature_flags";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_edit from "./message_edit";
import * as message_lists from "./message_lists";
import * as muted_users from "./muted_users";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";

export function get_actions_popover_content_context(message_id) {
    const message = message_lists.current.get(message_id);
    const message_container = message_lists.current.view.message_containers.get(message.id);
    const not_spectator = !page_params.is_spectator;
    const should_display_hide_option =
        muted_users.is_user_muted(message.sender_id) &&
        !message_container.is_hidden &&
        not_spectator;
    const editability = message_edit.get_editability(message);
    const can_move_message = message_edit.can_move_message(message);

    let editability_menu_item;
    let move_message_menu_item;
    let view_source_menu_item;

    if (editability === message_edit.editability_types.FULL) {
        editability_menu_item = $t({defaultMessage: "Edit message"});
        if (message.is_stream) {
            move_message_menu_item = $t({defaultMessage: "Move messages"});
        }
    } else if (can_move_message) {
        move_message_menu_item = $t({defaultMessage: "Move messages"});
        view_source_menu_item = $t({defaultMessage: "View message source"});
    } else {
        view_source_menu_item = $t({defaultMessage: "View message source"});
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

    const should_display_edit_history_option =
        message.edit_history &&
        message.edit_history.some(
            (entry) =>
                entry.prev_content !== undefined ||
                entry.prev_stream !== undefined ||
                entry.prev_topic !== undefined,
        ) &&
        page_params.realm_allow_edit_history &&
        not_spectator;

    // Disabling this for /me messages is a temporary workaround
    // for the fact that we don't have a styling for how that
    // should look.  See also condense.js.
    const should_display_collapse =
        !message.locally_echoed && !message.is_me_message && !message.collapsed && not_spectator;
    const should_display_uncollapse =
        !message.locally_echoed && !message.is_me_message && message.collapsed;

    const should_display_quote_and_reply = message.content !== "<p>(deleted)</p>" && not_spectator;

    const conversation_time_uri = hash_util.by_conversation_and_time_url(message);

    const should_display_delete_option = message_edit.get_deletability(message) && not_spectator;
    const should_display_read_receipts_option =
        page_params.realm_enable_read_receipts && not_spectator;

    return {
        message_id: message.id,
        stream_id: message.stream_id,
        editability_menu_item,
        move_message_menu_item,
        should_display_mark_as_unread,
        view_source_menu_item,
        should_display_collapse,
        should_display_uncollapse,
        should_display_add_reaction_option: message.sent_by_me,
        should_display_edit_history_option,
        should_display_hide_option,
        conversation_time_uri,
        narrowed: narrow_state.active(),
        should_display_delete_option,
        should_display_read_receipts_option,
        should_display_reminder_option: feature_flags.reminders_in_message_action_menu,
        should_display_quote_and_reply,
    };
}
