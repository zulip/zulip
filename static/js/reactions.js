const render_message_reaction = require('../templates/message_reaction.hbs');
const Dict = require('./dict').Dict;

exports.view = {}; // function namespace

exports.get_local_reaction_id = function (reaction_info) {
    return [
        reaction_info.reaction_type,
        reaction_info.emoji_name,
        reaction_info.emoji_code,
    ].join(',');
};

exports.get_reaction_info = function (reaction_id) {
    const reaction_info = reaction_id.split(',');
    return {
        reaction_type: reaction_info[0],
        emoji_name: reaction_info[1],
        emoji_code: reaction_info[2],
    };
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

exports.current_user_has_reacted_to_emoji = function (message, emoji_code, type) {
    const user_id = page_params.user_id;
    return _.any(message.reactions, function (r) {
        return r.user.id === user_id &&
               r.reaction_type === type &&
               r.emoji_code === emoji_code;
    });
};

function get_message(message_id) {
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error('reactions: Bad message id: ' + message_id);
        return;
    }

    return message;
}

function create_reaction(message_id, reaction_info) {
    return {
        message_id: message_id,
        user: {
            user_id: page_params.user_id,
            id: page_params.user_id,
        },
        local_id: exports.get_local_reaction_id(reaction_info),
        reaction_type: reaction_info.reaction_type,
        emoji_name: reaction_info.emoji_name,
        emoji_code: reaction_info.emoji_code,
    };
}

function update_ui_and_send_reaction_ajax(message_id, reaction_info) {
    const message = get_message(message_id);
    const has_reacted = exports.current_user_has_reacted_to_emoji(
        message,
        reaction_info.emoji_code,
        reaction_info.reaction_type
    );
    const operation = has_reacted ? 'remove' : 'add';
    const reaction = create_reaction(message_id, reaction_info);

    if (operation === "add") {
        exports.add_reaction(reaction);
    } else {
        exports.remove_reaction(reaction);
    }

    const args = {
        url: '/json/messages/' + message_id + '/reactions',
        data: reaction_info,
        success: function () {},
        error: function (xhr) {
            const response = channel.xhr_error_message("Error sending reaction", xhr);
            // Errors are somewhat commmon here, due to race conditions
            // where the user tries to add/remove the reaction when there is already
            // an in-flight request.  We eventually want to make this a blueslip
            // error, rather than a warning, but we need to implement either
            // #4291 or #4295 first.
            blueslip.warn(response);
        },
    };
    if (operation === 'add') {
        channel.post(args);
    } else if (operation === 'remove') {
        channel.del(args);
    }
}

function get_user_list_for_message_reaction(message, local_id) {
    const matching_reactions = message.reactions.filter(function (reaction) {
        return reaction.local_id === local_id;
    });
    return matching_reactions.map(function (reaction) {
        return reaction.user.id;
    });
}

exports.toggle_emoji_reaction = function (message_id, emoji_name) {
    // This codepath doesn't support toggling a deactivated realm emoji.
    // Since an user can interact with a deactivated realm emoji only by
    // clicking on a reaction and that is handled by `process_reaction_click()`
    // method. This codepath is to be used only where there is no chance of an
    // user interacting with a deactivated realm emoji like emoji picker.
    const reaction_info = {
        emoji_name: emoji_name,
    };

    if (emoji.active_realm_emojis.hasOwnProperty(emoji_name)) {
        if (emoji_name === 'zulip') {
            reaction_info.reaction_type = 'zulip_extra_emoji';
        } else {
            reaction_info.reaction_type = 'realm_emoji';
        }
        reaction_info.emoji_code = emoji.active_realm_emojis[emoji_name].id;
    } else if (emoji_codes.name_to_codepoint.hasOwnProperty(emoji_name)) {
        reaction_info.reaction_type = 'unicode_emoji';
        reaction_info.emoji_code = emoji_codes.name_to_codepoint[emoji_name];
    } else {
        blueslip.warn('Bad emoji name: ' + emoji_name);
        return;
    }

    update_ui_and_send_reaction_ajax(message_id, reaction_info);

    // The next line isn't always necessary, but it is harmless/quick
    // when no popovers are there.
    emoji_picker.hide_emoji_popover();
};

exports.process_reaction_click = function (message_id, local_id) {
    const reaction_info = exports.get_reaction_info(local_id);

    update_ui_and_send_reaction_ajax(message_id, reaction_info);
};

function full_name(user_id) {
    if (user_id === page_params.user_id) {
        return 'You (click to remove)';
    }
    return people.get_person_from_user_id(user_id).full_name;
}

function generate_title(emoji_name, user_ids) {
    const i = user_ids.indexOf(page_params.user_id);
    if (i !== -1) {
        // Move current user's id to start of list
        user_ids.splice(i, 1);
        user_ids.unshift(page_params.user_id);
    }
    const reacted_with_string = ' reacted with :' + emoji_name + ':';
    const user_names = user_ids.map(full_name);
    if (user_names.length === 1) {
        return user_names[0] + reacted_with_string;
    }
    return _.initial(user_names).join(', ') + ' and ' + _.last(user_names) + reacted_with_string;
}

// Add a tooltip showing who reacted to a message.
exports.get_reaction_title_data = function (message_id, local_id) {
    const message = get_message(message_id);
    const user_list = get_user_list_for_message_reaction(message, local_id);
    const emoji_name = exports.get_reaction_info(local_id).emoji_name;
    const title = generate_title(emoji_name, user_list);

    return title;
};

exports.get_reaction_section = function (message_id) {
    const message_element = $('.message_table').find("[zid='" + message_id + "']");
    const section = message_element.find('.message_reactions');
    return section;
};

exports.find_reaction = function (message_id, local_id) {
    const reaction_section = exports.get_reaction_section(message_id);
    const reaction = reaction_section.find("[data-reaction-id='" + local_id + "']");
    return reaction;
};

exports.get_add_reaction_button = function (message_id) {
    const reaction_section = exports.get_reaction_section(message_id);
    const add_button = reaction_section.find('.reaction_button');
    return add_button;
};

exports.set_reaction_count = function (reaction, count) {
    const count_element = reaction.find('.message_reaction_count');
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

    const reacted = exports.current_user_has_reacted_to_emoji(message,
                                                              event.emoji_code,
                                                              event.reaction_type);
    if (reacted && event.user.user_id === page_params.user_id) {
        return;
    }

    event.user.id = event.user.user_id;
    event.local_id = exports.get_local_reaction_id(event);

    message.reactions.push(event);

    const user_list = get_user_list_for_message_reaction(message, event.local_id);
    const opts = {
        message_id: event.message_id,
        reaction_type: event.reaction_type,
        emoji_name: event.emoji_name,
        emoji_code: event.emoji_code,
        user_id: event.user.id,
    };

    if (user_list.length > 1) {
        opts.user_list = user_list;
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
    reaction.attr('aria-label', new_label);

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
        message_id: message_id,
        emoji_name: emoji_name,
        emoji_code: emoji_code,
    };

    const new_label = generate_title(emoji_name, user_list);

    if (opts.reaction_type !== 'unicode_emoji') {
        context.is_realm_emoji = true;
        context.url = emoji.all_realm_emojis[emoji_code].emoji_url;
    }

    context.count = 1;
    context.label = new_label;
    context.local_id = exports.get_local_reaction_id(opts);
    context.emoji_alt_code = page_params.emojiset === 'text';

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
    const user_id = event.user.user_id;
    let i = -1;
    const message = message_store.get(message_id);
    const local_id = exports.get_local_reaction_id(event);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    const not_reacted = !exports.current_user_has_reacted_to_emoji(message,
                                                                   emoji_code,
                                                                   reaction_type);
    if (not_reacted && event.user.user_id === page_params.user_id) {
        return;
    }

    // Do the data part first:
    // Remove reactions from our message object.
    _.each(message.reactions, function (reaction, index) {
        if (reaction.local_id === local_id && reaction.user.id === user_id) {
            i = index;
        }
    });

    if (i !== -1) {
        message.reactions.splice(i, 1);
    }

    // Compute the new user list for this reaction.
    const user_list = get_user_list_for_message_reaction(message, local_id);

    exports.view.remove_reaction({
        message_id: message_id,
        reaction_type: reaction_type,
        emoji_name: emoji_name,
        emoji_code: emoji_code,
        user_list: user_list,
        user_id: user_id,
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
    reaction.attr('aria-label', new_label);

    // If the user is the current user, turn off the "reacted" class.

    exports.set_reaction_count(reaction, user_list.length);

    if (user_id === page_params.user_id) {
        reaction.removeClass("reacted");
    }
};

exports.get_emojis_used_by_user_for_message_id = function (message_id) {
    const user_id = page_params.user_id;
    const message = message_store.get(message_id);
    const reactions_by_user = message.reactions.filter(function (reaction) {
        return reaction.user.id === user_id;
    });
    return reactions_by_user.map(function (reaction) {
        return reaction.emoji_name;
    });
};

exports.get_message_reactions = function (message) {
    const message_reactions = new Dict();
    _.each(message.reactions, function (reaction) {
        const user_id = reaction.user.id;
        reaction.local_id = exports.get_local_reaction_id(reaction);
        if (!people.is_known_user_id(user_id)) {
            blueslip.warn('Unknown user_id ' + user_id +
                          ' in reaction for message ' + message.id);
            return;
        }
        reaction.user_ids = [];
        let collapsed_reaction = message_reactions.get(reaction.local_id);
        if (collapsed_reaction === undefined) {
            collapsed_reaction = _.omit(reaction, 'user');
            message_reactions.set(reaction.local_id, collapsed_reaction);
        }
        collapsed_reaction.user_ids.push(user_id);
    });
    const reactions = message_reactions.items().map(function (item) {
        const reaction = item[1];
        reaction.local_id = reaction.local_id;
        reaction.reaction_type = reaction.reaction_type;
        reaction.emoji_name = reaction.emoji_name;
        reaction.emoji_code = reaction.emoji_code;
        reaction.count = reaction.user_ids.length;
        reaction.label = generate_title(reaction.emoji_name, reaction.user_ids);
        reaction.emoji_alt_code = page_params.emojiset === 'text';

        if (reaction.reaction_type !== 'unicode_emoji') {
            reaction.is_realm_emoji = true;
            reaction.url = emoji.all_realm_emojis[reaction.emoji_code].emoji_url;
        }
        if (reaction.user_ids.indexOf(page_params.user_id) !== -1) {
            reaction.class = "message_reaction reacted";
        } else {
            reaction.class = "message_reaction";
        }
        return reaction;
    });
    return reactions;
};

window.reactions = exports;
