"use strict";

const _ = require("lodash");

const emoji = require("../shared/js/emoji");
const render_message_reaction = require("../templates/message_reaction.hbs");

const people = require("./people");

exports.view = {}; // function namespace

exports.get_local_reaction_id = function (reaction_info) {
    return [reaction_info.reaction_type, reaction_info.emoji_code].join(",");
};

exports.open_reactions_popover = function () {
    const message = current_msg_list.selected_message();
    let target = $(current_msg_list.selected_row()).find(".actions_hover")[0];
    if (!message.sent_by_me) {
        target = $(current_msg_list.selected_row()).find(".reaction_button")[0];
    }
    emoji_picker.toggle_emoji_popover(target, current_msg_list.selected_id());
    return true;
};

exports.current_user_has_reacted_to_emoji = function (message, local_id) {
    exports.set_clean_reactions(message);

    const r = message.clean_reactions.get(local_id);
    return r && r.user_ids.includes(page_params.user_id);
};

function get_message(message_id) {
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error("reactions: Bad message id: " + message_id);
        return;
    }

    exports.set_clean_reactions(message);
    return message;
}

function create_reaction(message_id, reaction_info) {
    return {
        message_id,
        user_id: page_params.user_id,
        local_id: exports.get_local_reaction_id(reaction_info),
        reaction_type: reaction_info.reaction_type,
        emoji_name: reaction_info.emoji_name,
        emoji_code: reaction_info.emoji_code,
    };
}

function update_ui_and_send_reaction_ajax(message_id, reaction_info) {
    const message = get_message(message_id);
    const local_id = exports.get_local_reaction_id(reaction_info);
    const has_reacted = exports.current_user_has_reacted_to_emoji(message, local_id);
    const operation = has_reacted ? "remove" : "add";
    const reaction = create_reaction(message_id, reaction_info);

    if (operation === "add") {
        exports.add_reaction(reaction);
    } else {
        exports.remove_reaction(reaction);
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

exports.toggle_emoji_reaction = function (message_id, emoji_name) {
    // This codepath doesn't support toggling a deactivated realm emoji.
    // Since an user can interact with a deactivated realm emoji only by
    // clicking on a reaction and that is handled by `process_reaction_click()`
    // method. This codepath is to be used only where there is no chance of an
    // user interacting with a deactivated realm emoji like emoji picker.
    const reaction_info = {
        emoji_name,
    };

    if (emoji.active_realm_emojis.has(emoji_name)) {
        if (emoji_name === "zulip") {
            reaction_info.reaction_type = "zulip_extra_emoji";
        } else {
            reaction_info.reaction_type = "realm_emoji";
        }
        reaction_info.emoji_code = emoji.active_realm_emojis.get(emoji_name).id;
    } else {
        const codepoint = emoji.get_emoji_codepoint(emoji_name);
        if (codepoint === undefined) {
            blueslip.warn("Bad emoji name: " + emoji_name);
            return;
        }
        reaction_info.reaction_type = "unicode_emoji";
        reaction_info.emoji_code = codepoint;
    }

    update_ui_and_send_reaction_ajax(message_id, reaction_info);
};

exports.process_reaction_click = function (message_id, local_id) {
    const message = get_message(message_id);

    if (!message) {
        blueslip.error("message_id for reaction click is unknown: " + message_id);
        return;
    }

    const r = message.clean_reactions.get(local_id);

    if (!r) {
        blueslip.error(
            "Data integrity problem for reaction " + local_id + " (message " + message_id + ")",
        );
        return;
    }

    const reaction_info = {
        reaction_type: r.reaction_type,
        emoji_name: r.emoji_name,
        emoji_code: r.emoji_code,
    };

    update_ui_and_send_reaction_ajax(message_id, reaction_info);
};

function full_name(user_id) {
    if (user_id === page_params.user_id) {
        return "You (click to remove)";
    }
    return people.get_by_user_id(user_id).full_name;
}

function generate_title(emoji_name, user_ids) {
    const i = user_ids.indexOf(page_params.user_id);
    if (i !== -1) {
        // Move current user's id to start of list
        user_ids.splice(i, 1);
        user_ids.unshift(page_params.user_id);
    }
    const reacted_with_string = " reacted with :" + emoji_name + ":";
    const user_names = user_ids.map(full_name);
    if (user_names.length === 1) {
        return user_names[0] + reacted_with_string;
    }
    return _.initial(user_names).join(", ") + " and " + _.last(user_names) + reacted_with_string;
}

// Add a tooltip showing who reacted to a message.
exports.get_reaction_title_data = function (message_id, local_id) {
    const message = get_message(message_id);

    const r = message.clean_reactions.get(local_id);
    const user_list = r.user_ids;
    const emoji_name = r.emoji_name;
    const title = generate_title(emoji_name, user_list);

    return title;
};

exports.get_reaction_section = function (message_id) {
    const message_element = $(".message_table").find("[zid='" + message_id + "']");
    const section = message_element.find(".message_reactions");
    return section;
};

exports.find_reaction = function (message_id, local_id) {
    const reaction_section = exports.get_reaction_section(message_id);
    const reaction = reaction_section.find("[data-reaction-id='" + local_id + "']");
    return reaction;
};

exports.get_add_reaction_button = function (message_id) {
    const reaction_section = exports.get_reaction_section(message_id);
    const add_button = reaction_section.find(".reaction_button");
    return add_button;
};

exports.set_reaction_count = function (reaction, count) {
    const count_element = reaction.find(".message_reaction_count");
    count_element.text(count);
};

exports.add_reaction = function (event) {
    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    exports.set_clean_reactions(message);

    const local_id = exports.get_local_reaction_id(event);
    const user_id = event.user_id;

    const r = message.clean_reactions.get(local_id);

    if (r && r.user_ids.includes(user_id)) {
        return;
    }

    if (r) {
        r.user_ids.push(user_id);
        exports.update_user_fields(r);
    } else {
        exports.add_clean_reaction({
            message,
            local_id,
            user_ids: [user_id],
            reaction_type: event.reaction_type,
            emoji_name: event.emoji_name,
            emoji_code: event.emoji_code,
        });
    }

    const opts = {
        message_id,
        reaction_type: event.reaction_type,
        emoji_name: event.emoji_name,
        emoji_code: event.emoji_code,
        user_id,
    };

    if (r) {
        opts.user_list = r.user_ids;
        exports.view.update_existing_reaction(opts);
    } else {
        exports.view.insert_new_reaction(opts);
    }
};

exports.view.update_existing_reaction = function (opts) {
    // Our caller ensures that this message already has a reaction
    // for this emoji and sets up our user_list.  This function
    // simply updates the DOM.

    const message_id = opts.message_id;
    const emoji_name = opts.emoji_name;
    const user_list = opts.user_list;
    const user_id = opts.user_id;
    const local_id = exports.get_local_reaction_id(opts);
    const reaction = exports.find_reaction(message_id, local_id);

    exports.set_reaction_count(reaction, user_list.length);

    const new_label = generate_title(emoji_name, user_list);
    reaction.attr("aria-label", new_label);

    if (user_id === page_params.user_id) {
        reaction.addClass("reacted");
    }
};

exports.view.insert_new_reaction = function (opts) {
    // Our caller ensures we are the first user to react to this
    // message with this emoji, and it populates user_list for
    // us.  We then render the emoji/title/count and insert it
    // before the add button.

    const message_id = opts.message_id;
    const emoji_name = opts.emoji_name;
    const emoji_code = opts.emoji_code;
    const user_id = opts.user_id;
    const user_list = [user_id];

    const context = {
        message_id,
        emoji_name,
        emoji_code,
    };

    const new_label = generate_title(emoji_name, user_list);

    if (opts.reaction_type !== "unicode_emoji") {
        context.is_realm_emoji = true;
        context.url = emoji.all_realm_emojis.get(emoji_code).emoji_url;
    }

    context.count = 1;
    context.label = new_label;
    context.local_id = exports.get_local_reaction_id(opts);
    context.emoji_alt_code = page_params.emojiset === "text";

    if (opts.user_id === page_params.user_id) {
        context.class = "message_reaction reacted";
    } else {
        context.class = "message_reaction";
    }

    const new_reaction = $(render_message_reaction(context));

    // Now insert it before the add button.
    const reaction_button_element = exports.get_add_reaction_button(message_id);
    new_reaction.insertBefore(reaction_button_element);
};

exports.remove_reaction = function (event) {
    const reaction_type = event.reaction_type;
    const emoji_name = event.emoji_name;
    const emoji_code = event.emoji_code;
    const message_id = event.message_id;
    const user_id = event.user_id;
    const message = message_store.get(message_id);
    const local_id = exports.get_local_reaction_id(event);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    exports.set_clean_reactions(message);

    const r = message.clean_reactions.get(local_id);

    if (!r) {
        return;
    }

    if (!r.user_ids.includes(user_id)) {
        return;
    }

    r.user_ids = r.user_ids.filter((id) => id !== user_id);
    if (r.user_ids.length > 0) {
        exports.update_user_fields(r);
    } else {
        message.clean_reactions.delete(local_id);
    }

    exports.view.remove_reaction({
        message_id,
        reaction_type,
        emoji_name,
        emoji_code,
        user_list: r.user_ids,
        user_id,
    });
};

exports.view.remove_reaction = function (opts) {
    const message_id = opts.message_id;
    const emoji_name = opts.emoji_name;
    const user_list = opts.user_list;
    const user_id = opts.user_id;
    const local_id = exports.get_local_reaction_id(opts);
    const reaction = exports.find_reaction(message_id, local_id);

    if (user_list.length === 0) {
        // If this user was the only one reacting for this emoji, we simply
        // remove the reaction and exit.
        reaction.remove();
        return;
    }

    // The emoji still has reactions from other users, so we need to update
    // the title/count and, if the user is the current user, turn off the
    // "reacted" class.

    const new_label = generate_title(emoji_name, user_list);
    reaction.attr("aria-label", new_label);

    // If the user is the current user, turn off the "reacted" class.

    exports.set_reaction_count(reaction, user_list.length);

    if (user_id === page_params.user_id) {
        reaction.removeClass("reacted");
    }
};

exports.get_emojis_used_by_user_for_message_id = function (message_id) {
    const user_id = page_params.user_id;
    const message = message_store.get(message_id);
    exports.set_clean_reactions(message);

    const names = [];
    for (const r of message.clean_reactions.values()) {
        if (r.user_ids.includes(user_id)) {
            names.push(r.emoji_name);
        }
    }

    return names;
};

exports.get_message_reactions = function (message) {
    exports.set_clean_reactions(message);
    return Array.from(message.clean_reactions.values());
};

exports.set_clean_reactions = function (message) {
    /*
        The server sends us a single structure for
        each reaction, even if two users are reacting
        with the same emoji.  Our first loop creates
        a map of distinct reactions and a map of
        local_id -> user_ids.  The `local_id` is
        basically a key for the emoji name.

        Then in our second loop we build a more compact
        data structure that's easier for our message
        list view templates to work with.
    */

    if (message.clean_reactions) {
        return;
    }

    const distinct_reactions = new Map();
    const user_map = new Map();

    for (const reaction of message.reactions) {
        const local_id = exports.get_local_reaction_id(reaction);
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

    /*
        It might feel a little janky to attach clean_reactions
        directly to the message object, but this allows the
        server to send us a new copy of the message, and then
        the next time we try to get reactions from it, we
        won't have `clean_reactions`, and we will re-process
        the server's latest copy of the reactions.
    */
    message.clean_reactions = new Map();

    for (const local_id of distinct_reactions.keys()) {
        const reaction = distinct_reactions.get(local_id);
        const user_ids = user_map.get(local_id);

        exports.add_clean_reaction({
            message,
            local_id,
            user_ids,
            reaction_type: reaction.reaction_type,
            emoji_name: reaction.emoji_name,
            emoji_code: reaction.emoji_code,
        });
    }
};

exports.add_clean_reaction = function (opts) {
    const r = {};

    r.reaction_type = opts.reaction_type;
    r.emoji_name = opts.emoji_name;
    r.emoji_code = opts.emoji_code;
    r.local_id = opts.local_id;

    r.user_ids = opts.user_ids;
    exports.update_user_fields(r);

    r.emoji_alt_code = page_params.emojiset === "text";

    if (r.reaction_type !== "unicode_emoji") {
        r.is_realm_emoji = true;
        r.url = emoji.all_realm_emojis.get(r.emoji_code).emoji_url;
    }

    opts.message.clean_reactions.set(opts.local_id, r);
};

exports.update_user_fields = function (r) {
    r.count = r.user_ids.length;
    r.label = generate_title(r.emoji_name, r.user_ids);
    if (r.user_ids.includes(page_params.user_id)) {
        r.class = "message_reaction reacted";
    } else {
        r.class = "message_reaction";
    }
};

window.reactions = exports;
