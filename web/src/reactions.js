import $ from "jquery";

import render_message_reaction from "../templates/message_reaction.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as emoji from "./emoji";
import {$t} from "./i18n";
import * as message_store from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as spectators from "./spectators";
import {user_settings} from "./user_settings";

export const view = {
    waiting_for_server_request_ids: new Set(),
}; // function namespace

export function get_local_reaction_id(reaction_info) {
    return [reaction_info.reaction_type, reaction_info.emoji_code].join(",");
}

export function current_user_has_reacted_to_emoji(message, local_id) {
    set_clean_reactions(message);

    const clean_reaction_object = message.clean_reactions.get(local_id);
    return clean_reaction_object && clean_reaction_object.user_ids.includes(page_params.user_id);
}

function get_message(message_id) {
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error("reactions: Bad message id", {message_id});
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

    // To avoid duplicate requests to the server, we construct a
    // unique request ID combining the message ID and the local ID,
    // which identifies just which emoji to use.
    const reaction_request_id = [message_id, local_id].join(",");
    if (view.waiting_for_server_request_ids.has(reaction_request_id)) {
        return;
    }

    if (operation === "add") {
        add_reaction(reaction);
    } else {
        remove_reaction(reaction);
    }

    const args = {
        url: "/json/messages/" + message_id + "/reactions",
        data: reaction_info,
        success() {
            view.waiting_for_server_request_ids.delete(reaction_request_id);
        },
        error(xhr) {
            view.waiting_for_server_request_ids.delete(reaction_request_id);
            if (xhr.readyState !== 0) {
                if (
                    xhr.responseJSON?.code === "REACTION_ALREADY_EXISTS" ||
                    xhr.responseJSON?.code === "REACTION_DOES_NOT_EXIST"
                ) {
                    // Don't send error report for simple precondition failures caused by race
                    // conditions; the user already got what they wanted
                } else {
                    blueslip.error(channel.xhr_error_message("Error sending reaction", xhr));
                }
            }
        },
    };

    view.waiting_for_server_request_ids.add(reaction_request_id);
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
        blueslip.error("message_id for reaction click is unknown", {message_id});
        return;
    }

    const clean_reaction_object = message.clean_reactions.get(local_id);

    if (!clean_reaction_object) {
        blueslip.error("Data integrity problem for reaction", {local_id, message_id});
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
    const $message_element = $(".message-list").find(`[zid='${CSS.escape(message_id)}']`);
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

export function set_reaction_vote_text($reaction, vote_text) {
    const $count_element = $reaction.find(".message_reaction_count");
    $count_element.text(vote_text);
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
    let clean_reaction_object = message.clean_reactions.get(local_id);
    if (clean_reaction_object && clean_reaction_object.user_ids.includes(user_id)) {
        return;
    }

    if (clean_reaction_object) {
        clean_reaction_object.user_ids.push(user_id);
        update_user_fields(clean_reaction_object, message.clean_reactions);
        view.update_existing_reaction(clean_reaction_object, message, user_id);
    } else {
        clean_reaction_object = make_clean_reaction({
            local_id,
            user_ids: [user_id],
            reaction_type: event.reaction_type,
            emoji_name: event.emoji_name,
            emoji_code: event.emoji_code,
        });

        message.clean_reactions.set(local_id, clean_reaction_object);
        update_user_fields(clean_reaction_object, message.clean_reactions);
        view.insert_new_reaction(clean_reaction_object, message, user_id);
    }
}

view.update_existing_reaction = function (clean_reaction_object, message, acting_user_id) {
    // Our caller ensures that this message already has a reaction
    // for this emoji and sets up our user_list.  This function
    // simply updates the DOM.
    const local_id = get_local_reaction_id(clean_reaction_object);
    const $reaction = find_reaction(message.id, local_id);

    const new_label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );
    $reaction.attr("aria-label", new_label);

    if (acting_user_id === page_params.user_id) {
        $reaction.addClass("reacted");
    }

    update_vote_text_on_message(message);
};

view.insert_new_reaction = function (clean_reaction_object, message, user_id) {
    // Our caller ensures we are the first user to react to this
    // message with this emoji. We then render the emoji/title/count
    // and insert it before the add button.

    const context = {
        message_id: message.id,
        ...emoji.get_emoji_details_for_rendering(clean_reaction_object),
    };

    const new_label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );

    context.count = 1;
    context.label = new_label;
    context.local_id = get_local_reaction_id(clean_reaction_object);
    context.emoji_alt_code = user_settings.emojiset === "text";
    context.is_realm_emoji =
        context.reaction_type === "realm_emoji" || context.reaction_type === "zulip_extra_emoji";
    context.vote_text = ""; // Updated below

    if (user_id === page_params.user_id) {
        context.class = "message_reaction reacted";
    } else {
        context.class = "message_reaction";
    }

    const $new_reaction = $(render_message_reaction(context));

    // Now insert it before the add button.
    const $reaction_button_element = get_add_reaction_button(message.id);
    $new_reaction.insertBefore($reaction_button_element);

    update_vote_text_on_message(message);
};

export function remove_reaction(event) {
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
    if (clean_reaction_object.user_ids.length === 0) {
        message.clean_reactions.delete(local_id);
    }

    const should_display_reactors = check_should_display_reactors(message.clean_reactions);
    update_user_fields(clean_reaction_object, should_display_reactors);

    view.remove_reaction(clean_reaction_object, message, user_id);
}

view.remove_reaction = function (clean_reaction_object, message, user_id) {
    const local_id = get_local_reaction_id(clean_reaction_object);
    const $reaction = find_reaction(message.id, local_id);
    const reaction_count = clean_reaction_object.user_ids.length;

    if (reaction_count === 0) {
        // If this user was the only one reacting for this emoji, we simply
        // remove the reaction and exit.
        $reaction.remove();
        update_vote_text_on_message(message);
        return;
    }

    // The emoji still has reactions from other users, so we need to update
    // the title/count and, if the user is the current user, turn off the
    // "reacted" class.
    const new_label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );
    $reaction.attr("aria-label", new_label);
    if (user_id === page_params.user_id) {
        $reaction.removeClass("reacted");
    }

    update_vote_text_on_message(message);
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
    return [...message.clean_reactions.values()];
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
        // Update display details for the reaction. In particular,
        // user_settings.display_emoji_reaction_users or the names of
        // the users appearing in the reaction may have changed since
        // this reaction was first rendered.
        const should_display_reactors = check_should_display_reactors(message.clean_reactions);
        for (const clean_reaction of message.clean_reactions.values()) {
            update_user_fields(clean_reaction, should_display_reactors);
        }
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
            blueslip.error("server sent duplicate reactions", {user_id, local_id});
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

    // We do update_user_fields in a separate loop, because doing so
    // lets us avoid duplicating check_should_display_reactors to
    // determine whether to store in the vote_text field a count or
    // the names of reactors (users who reacted).
    const should_display_reactors = check_should_display_reactors(message.clean_reactions);
    for (const clean_reaction of message.clean_reactions.values()) {
        update_user_fields(clean_reaction, should_display_reactors);
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
    return clean_reaction_object;
}

export function update_user_fields(clean_reaction_object, should_display_reactors) {
    // update_user_fields needs to be called whenever the set of users
    // whor eacted on a message might have changed, including due to
    // upvote/downvotes on ANY reaction in the message, because those
    // can change the correct value of should_display_reactors to use.
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

    clean_reaction_object.count = clean_reaction_object.user_ids.length;
    clean_reaction_object.label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );

    // The vote_text field set here is used directly in the Handlebars
    // template for rendering (or rerendering!) a message.
    clean_reaction_object.vote_text = get_vote_text(clean_reaction_object, should_display_reactors);
}

export function get_vote_text(clean_reaction_object, should_display_reactors) {
    if (should_display_reactors) {
        return comma_separated_usernames(clean_reaction_object.user_ids);
    }
    return `${clean_reaction_object.user_ids.length}`;
}

function check_should_display_reactors(cleaned_reactions) {
    if (!user_settings.display_emoji_reaction_users) {
        return false;
    }

    let total_reactions = 0;
    for (const r of cleaned_reactions.values()) {
        // r.count is not yet initialized when this is called during
        // set_clean_reactions.
        total_reactions += r.count || r.user_ids.length;
    }
    return total_reactions <= 3;
}

function comma_separated_usernames(user_list) {
    const usernames = people.get_display_full_names(user_list);
    const current_user_has_reacted = user_list.includes(page_params.user_id);

    if (current_user_has_reacted) {
        const current_user_index = user_list.indexOf(page_params.user_id);
        usernames[current_user_index] = $t({
            defaultMessage: "You",
        });
    }
    const comma_separated_usernames = usernames.join(", ");
    return comma_separated_usernames;
}

export function update_vote_text_on_message(message) {
    // Because whether we display a count or the names of reacting
    // users depends on total reactions on the message, we need to
    // recalculate this whenever adjusting reaction rendering on a
    // message.
    const cleaned_reactions = get_message_reactions(message);
    const should_display_reactors = check_should_display_reactors(cleaned_reactions);
    for (const [reaction, clean_reaction] of message.clean_reactions.entries()) {
        const reaction_elem = find_reaction(message.id, clean_reaction.local_id);
        const vote_text = get_vote_text(clean_reaction, should_display_reactors);
        message.clean_reactions.get(reaction).vote_text = vote_text;
        set_reaction_vote_text(reaction_elem, vote_text);
    }
}
