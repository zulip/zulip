import $ from "jquery";

import render_message_reaction from "../templates/message_reaction.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as emoji from "./emoji";
import * as emoji_picker from "./emoji_picker";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as spectators from "./spectators";
import {user_settings} from "./user_settings";

export const view = {}; // function namespace

export function get_local_reaction_id(reaction_info) {
    return [reaction_info.reaction_type, reaction_info.emoji_code].join(",");
}

export function open_reactions_popover() {
    const message = message_lists.current.selected_message();
    let target;

    // Use verbose style to ensure we test both sides of the condition.
    if (message.sent_by_me) {
        target = $(message_lists.current.selected_row()).find(".actions_hover")[0];
    } else {
        target = $(message_lists.current.selected_row()).find(".reaction_button")[0];
    }

    emoji_picker.toggle_emoji_popover(target, message_lists.current.selected_id());
    return true;
}

export function current_user_has_reacted_to_emoji(message, local_id) {
    set_clean_reactions(message);

    const clean_reaction_object = message.clean_reactions.get(local_id);
    return clean_reaction_object && clean_reaction_object.user_ids.includes(page_params.user_id);
}

function get_message(message_id) {
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error("reactions: Bad message id: " + message_id);
        return undefined;
    }

    set_clean_reactions(message);
    return message;
}

function create_reaction(message_id, reaction_info) {
    return {
        message_id,
        user_id: page_params.user_id,
        local_id: get_local_reaction_id(reaction_info),
        reaction_type: reaction_info.reaction_type,
        emoji_name: reaction_info.emoji_name,
        emoji_code: reaction_info.emoji_code,
    };
}

function update_ui_and_send_reaction_ajax(message_id, reaction_info) {
    if (page_params.is_spectator) {
        // Spectators can't react, since they don't have accounts.  We
        // stop here to avoid a confusing reaction local echo.
        spectators.login_to_access();
        return;
    }

    const message = get_message(message_id);
    const local_id = get_local_reaction_id(reaction_info);
    const has_reacted = current_user_has_reacted_to_emoji(message, local_id);
    const operation = has_reacted ? "remove" : "add";
    const reaction = create_reaction(message_id, reaction_info);

    if (operation === "add") {
        add_reaction(reaction);
    } else {
        remove_reaction(reaction);
    }

    const args = {
        url: "/json/messages/" + message_id + "/reactions",
        data: reaction_info,
        success() {},
        error(xhr) {
            const response = channel.xhr_error_message("Error sending reaction", xhr);
            // Errors are somewhat common here, due to race conditions
            // where the user tries to add/remove the reaction when there is already
            // an in-flight request.  We eventually want to make this a blueslip
            // error, rather than a warning, but we need to implement either
            // #4291 or #4295 first.
            blueslip.warn(response);
        },
    };
    if (operation === "add") {
        channel.post(args);
    } else if (operation === "remove") {
        channel.del(args);
    }
}

export function toggle_emoji_reaction(message_id, emoji_name) {
    // This codepath doesn't support toggling a deactivated realm emoji.
    // Since an user can interact with a deactivated realm emoji only by
    // clicking on a reaction and that is handled by `process_reaction_click()`
    // method. This codepath is to be used only where there is no chance of an
    // user interacting with a deactivated realm emoji like emoji picker.

    const reaction_info = emoji.get_emoji_details_by_name(emoji_name);
    update_ui_and_send_reaction_ajax(message_id, reaction_info);
}

export function process_reaction_click(message_id, local_id) {
    const message = get_message(message_id);

    if (!message) {
        blueslip.error("message_id for reaction click is unknown: " + message_id);
        return;
    }

    const clean_reaction_object = message.clean_reactions.get(local_id);

    if (!clean_reaction_object) {
        blueslip.error(
            "Data integrity problem for reaction " + local_id + " (message " + message_id + ")",
        );
        return;
    }

    const reaction_info = {
        reaction_type: clean_reaction_object.reaction_type,
        emoji_name: clean_reaction_object.emoji_name,
        emoji_code: clean_reaction_object.emoji_code,
    };

    update_ui_and_send_reaction_ajax(message_id, reaction_info);
}

function generate_title(emoji_name, user_ids) {
    const usernames = people.get_display_full_names(
        user_ids.filter((user_id) => user_id !== page_params.user_id),
    );
    const current_user_reacted = user_ids.length !== usernames.length;

    const context = {
        emoji_name: ":" + emoji_name + ":",
    };

    if (user_ids.length === 1) {
        if (current_user_reacted) {
            return $t({defaultMessage: "You (click to remove) reacted with {emoji_name}"}, context);
        }
        context.username = usernames[0];
        return $t({defaultMessage: "{username} reacted with {emoji_name}"}, context);
    }

    if (user_ids.length === 2 && current_user_reacted) {
        context.other_username = usernames[0];
        return $t(
            {
                defaultMessage:
                    "You (click to remove) and {other_username} reacted with {emoji_name}",
            },
            context,
        );
    }

    context.comma_separated_usernames = usernames.slice(0, -1).join(", ");
    context.last_username = usernames.at(-1);
    if (current_user_reacted) {
        return $t(
            {
                defaultMessage:
                    "You (click to remove), {comma_separated_usernames} and {last_username} reacted with {emoji_name}",
            },
            context,
        );
    }
    return $t(
        {
            defaultMessage:
                "{comma_separated_usernames} and {last_username} reacted with {emoji_name}",
        },
        context,
    );
}

// Add a tooltip showing who reacted to a message.
export function get_reaction_title_data(message_id, local_id) {
    const message = get_message(message_id);

    const clean_reaction_object = message.clean_reactions.get(local_id);
    const user_list = clean_reaction_object.user_ids;
    const emoji_name = clean_reaction_object.emoji_name;
    const title = generate_title(emoji_name, user_list);

    return title;
}

export function get_reaction_section(message_id) {
    const $message_element = $(".message_table").find(`[zid='${CSS.escape(message_id)}']`);
    const $section = $message_element.find(".message_reactions");
    return $section;
}

export function find_reaction(message_id, local_id) {
    const $reaction_section = get_reaction_section(message_id);
    const $reaction = $reaction_section.find(`[data-reaction-id='${CSS.escape(local_id)}']`);
    return $reaction;
}

export function get_add_reaction_button(message_id) {
    const $reaction_section = get_reaction_section(message_id);
    const $add_button = $reaction_section.find(".reaction_button");
    return $add_button;
}

export function set_reaction_count($reaction, count) {
    const $count_element = $reaction.find(".message_reaction_count");
    $count_element.text(count);
}

export function add_reaction(event) {
    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    set_clean_reactions(message);

    const local_id = get_local_reaction_id(event);
    const user_id = event.user_id;
    const clean_reaction_object = message.clean_reactions.get(local_id);
    if (clean_reaction_object && clean_reaction_object.user_ids.includes(user_id)) {
        return;
    }

    if (clean_reaction_object) {
        clean_reaction_object.user_ids.push(user_id);
        update_user_fields(clean_reaction_object);
    } else {
        message.clean_reactions.set(
            local_id,
            make_clean_reaction({
                local_id,
                user_ids: [user_id],
                reaction_type: event.reaction_type,
                emoji_name: event.emoji_name,
                emoji_code: event.emoji_code,
            }),
        );
    }

    const opts = {
        message_id,
        reaction_type: event.reaction_type,
        emoji_name: event.emoji_name,
        emoji_code: event.emoji_code,
        user_id,
    };

    if (clean_reaction_object) {
        opts.user_list = clean_reaction_object.user_ids;
        view.update_existing_reaction(opts);
    } else {
        view.insert_new_reaction(opts);
    }
}

view.update_existing_reaction = function ({
    message_id,
    emoji_name,
    user_list,
    user_id,
    reaction_type,
    emoji_code,
}) {
    // Our caller ensures that this message already has a reaction
    // for this emoji and sets up our user_list.  This function
    // simply updates the DOM.
    const local_id = get_local_reaction_id({reaction_type, emoji_code});
    const $reaction = find_reaction(message_id, local_id);

    set_reaction_count($reaction, user_list.length);

    const new_label = generate_title(emoji_name, user_list);
    $reaction.attr("aria-label", new_label);

    if (user_id === page_params.user_id) {
        $reaction.addClass("reacted");
    }
};

view.insert_new_reaction = function ({message_id, user_id, emoji_name, emoji_code, reaction_type}) {
    // Our caller ensures we are the first user to react to this
    // message with this emoji, and it populates user_list for
    // us.  We then render the emoji/title/count and insert it
    // before the add button.

    const user_list = [user_id];

    const context = {
        message_id,
        ...emoji.get_emoji_details_for_rendering({emoji_name, emoji_code, reaction_type}),
    };

    const new_label = generate_title(emoji_name, user_list);

    context.count = 1;
    context.label = new_label;
    context.local_id = get_local_reaction_id({reaction_type, emoji_code});
    context.emoji_alt_code = user_settings.emojiset === "text";
    context.is_realm_emoji =
        context.reaction_type === "realm_emoji" || context.reaction_type === "zulip_extra_emoji";

    if (user_id === page_params.user_id) {
        context.class = "message_reaction reacted";
    } else {
        context.class = "message_reaction";
    }

    const $new_reaction = $(render_message_reaction(context));

    // Now insert it before the add button.
    const $reaction_button_element = get_add_reaction_button(message_id);
    $new_reaction.insertBefore($reaction_button_element);
};

export function remove_reaction(event) {
    const reaction_type = event.reaction_type;
    const emoji_name = event.emoji_name;
    const emoji_code = event.emoji_code;
    const message_id = event.message_id;
    const user_id = event.user_id;
    const message = message_store.get(message_id);
    const local_id = get_local_reaction_id(event);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    set_clean_reactions(message);

    const clean_reaction_object = message.clean_reactions.get(local_id);

    if (!clean_reaction_object) {
        return;
    }

    if (!clean_reaction_object.user_ids.includes(user_id)) {
        return;
    }

    clean_reaction_object.user_ids = clean_reaction_object.user_ids.filter((id) => id !== user_id);
    if (clean_reaction_object.user_ids.length > 0) {
        update_user_fields(clean_reaction_object);
    } else {
        message.clean_reactions.delete(local_id);
    }

    view.remove_reaction({
        message_id,
        reaction_type,
        emoji_name,
        emoji_code,
        user_list: clean_reaction_object.user_ids,
        user_id,
    });
}

view.remove_reaction = function ({
    message_id,
    emoji_name,
    user_list,
    user_id,
    reaction_type,
    emoji_code,
}) {
    const local_id = get_local_reaction_id({reaction_type, emoji_code});
    const $reaction = find_reaction(message_id, local_id);

    if (user_list.length === 0) {
        // If this user was the only one reacting for this emoji, we simply
        // remove the reaction and exit.
        $reaction.remove();
        return;
    }

    // The emoji still has reactions from other users, so we need to update
    // the title/count and, if the user is the current user, turn off the
    // "reacted" class.

    const new_label = generate_title(emoji_name, user_list);
    $reaction.attr("aria-label", new_label);

    // If the user is the current user, turn off the "reacted" class.

    set_reaction_count($reaction, user_list.length);

    if (user_id === page_params.user_id) {
        $reaction.removeClass("reacted");
    }
};

export function get_emojis_used_by_user_for_message_id(message_id) {
    const user_id = page_params.user_id;
    const message = message_store.get(message_id);
    set_clean_reactions(message);

    const names = [];
    for (const clean_reaction_object of message.clean_reactions.values()) {
        if (clean_reaction_object.user_ids.includes(user_id)) {
            names.push(clean_reaction_object.emoji_name);
        }
    }

    return names;
}

export function get_message_reactions(message) {
    set_clean_reactions(message);
    return Array.from(message.clean_reactions.values());
}

export function set_clean_reactions(message) {
    /*
      set_clean_reactions processes the raw message.reactions object,
      which will contain one object for each individual reaction, even
      if two users react with the same emoji.

      As output, it sets message.cleaned_reactions, which is a more
      compressed format with one entry per reaction pill that should
      be displayed visually to users.
    */

    if (message.clean_reactions) {
        return;
    }

    // This first loop creates a temporary distinct_reactions data
    // structure, which will accumulate the set of users who have
    // reacted with each distinct reaction.
    const distinct_reactions = new Map();
    const user_map = new Map();
    for (const reaction of message.reactions) {
        const local_id = get_local_reaction_id(reaction);
        const user_id = reaction.user_id;

        if (!people.is_known_user_id(user_id)) {
            blueslip.warn("Unknown user_id " + user_id + " in reaction for message " + message.id);
            continue;
        }

        if (!distinct_reactions.has(local_id)) {
            distinct_reactions.set(local_id, reaction);
            user_map.set(local_id, []);
        }

        const user_ids = user_map.get(local_id);

        if (user_ids.includes(user_id)) {
            blueslip.error(
                "server sent duplicate reactions for user " + user_id + " (key=" + local_id + ")",
            );
            continue;
        }

        user_ids.push(user_id);
    }

    // TODO: Rather than adding this field to the message object, it
    // might be cleaner to create an independent map from message_id
    // => clean_reactions data for the message, with care being taken
    // to make sure reify_message_id moves the data structure
    // properly.
    message.clean_reactions = new Map();
    for (const local_id of distinct_reactions.keys()) {
        const reaction = distinct_reactions.get(local_id);
        const user_ids = user_map.get(local_id);

        message.clean_reactions.set(
            local_id,
            make_clean_reaction({local_id, user_ids, ...reaction}),
        );
    }

    // We don't maintain message.reactions when users react to
    // messages we already have a copy of, so it's safest to delete it
    // after we've processed the reactions data for a message into the
    // clean_reactions data structure, which we do maintain.
    delete message.reactions;
}

function make_clean_reaction({local_id, user_ids, emoji_name, emoji_code, reaction_type}) {
    const clean_reaction_object = {
        local_id,
        user_ids,
        ...emoji.get_emoji_details_for_rendering({emoji_name, emoji_code, reaction_type}),
    };
    clean_reaction_object.emoji_alt_code = user_settings.emojiset === "text";
    clean_reaction_object.is_realm_emoji =
        clean_reaction_object.reaction_type === "realm_emoji" ||
        clean_reaction_object.reaction_type === "zulip_extra_emoji";

    // Call update_user_fields last, so it can rely on
    // clean_reaction_object being otherwise fully populated.
    update_user_fields(clean_reaction_object);
    return clean_reaction_object;
}

export function update_user_fields(clean_reaction_object) {
    clean_reaction_object.count = clean_reaction_object.user_ids.length;
    clean_reaction_object.label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );
    if (clean_reaction_object.user_ids.includes(page_params.user_id)) {
        clean_reaction_object.class = "message_reaction reacted";
    } else {
        clean_reaction_object.class = "message_reaction";
    }
}
