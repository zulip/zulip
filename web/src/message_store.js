import * as blueslip from "./blueslip";
import * as people from "./people";

const stored_messages = new Map();

export function update_message_cache(message) {
    // You should only call this from message_helper (or in tests).
    stored_messages.set(message.id, message);
}

export function get_cached_message(message_id) {
    // You should only call this from message_helper.
    // Use the get() wrapper below for most other use cases.
    return stored_messages.get(message_id);
}

export function clear_for_testing() {
    stored_messages.clear();
}

export function get(message_id) {
    if (message_id === undefined || message_id === null) {
        blueslip.error("message_store.get got bad value", {message_id});
        return undefined;
    }

    if (typeof message_id !== "number") {
        blueslip.error("message_store got non-number", {message_id});

        // Try to soldier on, assuming the caller treats message
        // ids as strings.
        message_id = Number.parseFloat(message_id);
    }

    return stored_messages.get(message_id);
}

export function get_pm_emails(message) {
    const user_ids = people.pm_with_user_ids(message);
    const emails = user_ids
        .map((user_id) => {
            const person = people.maybe_get_user_by_id(user_id);
            if (!person) {
                blueslip.error("Unknown user id", {user_id});
                return "?";
            }
            return person.email;
        })
        .sort();

    return emails.join(", ");
}

export function get_pm_full_names(message) {
    const user_ids = people.pm_with_user_ids(message);
    const names = people.get_display_full_names(user_ids).sort();

    return names.join(", ");
}

export function set_message_booleans(message) {
    const flags = message.flags || [];

    function convert_flag(flag_name) {
        return flags.includes(flag_name);
    }

    message.unread = !convert_flag("read");
    message.historical = convert_flag("historical");
    message.starred = convert_flag("starred");
    message.mentioned = convert_flag("mentioned") || convert_flag("wildcard_mentioned");
    message.mentioned_me_directly = convert_flag("mentioned");
    message.wildcard_mentioned = convert_flag("wildcard_mentioned");
    message.collapsed = convert_flag("collapsed");
    message.alerted = convert_flag("has_alert_word");

    // Once we have set boolean flags here, the `flags` attribute is
    // just a distraction, so we delete it.  (All the downstream code
    // uses booleans.)
    delete message.flags;
}

export function update_booleans(message, flags) {
    // When we get server flags for local echo or message edits,
    // we are vulnerable to race conditions, so only update flags
    // that are driven by message content.
    function convert_flag(flag_name) {
        return flags.includes(flag_name);
    }

    message.mentioned = convert_flag("mentioned") || convert_flag("wildcard_mentioned");
    message.mentioned_me_directly = convert_flag("mentioned");
    message.wildcard_mentioned = convert_flag("wildcard_mentioned");
    message.alerted = convert_flag("has_alert_word");
}

export function update_property(property, value, info) {
    switch (property) {
        case "sender_full_name":
        case "small_avatar_url":
            for (const msg of stored_messages.values()) {
                if (msg.sender_id && msg.sender_id === info.user_id) {
                    msg[property] = value;
                }
            }
            break;
        case "stream_name":
            for (const msg of stored_messages.values()) {
                if (msg.stream_id && msg.stream_id === info.stream_id) {
                    msg.display_recipient = value;
                }
            }
            break;
        case "status_emoji_info":
            for (const msg of stored_messages.values()) {
                if (msg.sender_id && msg.sender_id === info.user_id) {
                    msg[property] = value;
                }
            }
            break;
    }
}

export function reify_message_id({old_id, new_id}) {
    if (stored_messages.has(old_id)) {
        stored_messages.set(new_id, stored_messages.get(old_id));
        stored_messages.delete(old_id);
    }
}
