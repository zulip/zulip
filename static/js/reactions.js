var reactions = (function () {
var exports = {};

exports.view = {}; // function namespace

exports.open_reactions_popover = function () {
    var message = current_msg_list.selected_message();
    var target = $(current_msg_list.selected_row()).find(".actions_hover")[0];
    if (!message.sent_by_me) {
        target = $(current_msg_list.selected_row()).find(".reaction_button")[0];
    }
    emoji_picker.toggle_emoji_popover(target, current_msg_list.selected_id());
    return true;
};

function send_reaction_ajax(message_id, emoji_name, operation) {
    if (!emoji.emojis_by_name[emoji_name] && !emoji.active_realm_emojis[emoji_name]) {
        // Emoji doesn't exist
        return;
    }
    var args = {
        url: '/json/messages/' + message_id + '/emoji_reactions/' + encodeURIComponent(emoji_name),
        data: {},
        success: function () {},
        error: function (xhr) {
            var response = channel.xhr_error_message("Error sending reaction", xhr);
            // Errors are somewhat commmon here, due to race conditions
            // where the user tries to add/remove the reaction when there is already
            // an in-flight request.  We eventually want to make this a blueslip
            // error, rather than a warning, but we need to implement either
            // #4291 or #4295 first.
            blueslip.warn(response);
        },
    };
    if (operation === 'add') {
        channel.put(args);
    } else if (operation === 'remove') {
        channel.del(args);
    }
}

exports.current_user_has_reacted_to_emoji = function (message, emoji_name) {
    var user_id = page_params.user_id;
    return _.any(message.reactions, function (r) {
        return (r.user.id === user_id) &&  (r.emoji_name === emoji_name);
    });
};

function get_user_list_for_message_reaction(message, emoji_name) {
    var matching_reactions = message.reactions.filter(function (reaction) {
        return reaction.emoji_name === emoji_name;
    });
    return matching_reactions.map(function (reaction) {
        return reaction.user.id;
    });
}

function get_message(message_id) {
    var message = message_store.get(message_id);
    if (!message) {
        blueslip.error('reactions: Bad message id: ' + message_id);
        return;
    }

    return message;
}

exports.toggle_emoji_reaction = function (message_id, emoji_name) {
    // This toggles the current user's reaction to the clicked emoji.

    var message = get_message(message_id);
    if (!message) {
        return;
    }

    var has_reacted = exports.current_user_has_reacted_to_emoji(message, emoji_name);
    var operation = has_reacted ? 'remove' : 'add';

    send_reaction_ajax(message_id, emoji_name, operation);

    // The next line isn't always necessary, but it is harmless/quick
    // when no popovers are there.
    emoji_picker.hide_emoji_popover();
};

function full_name(user_id) {
    if (user_id === page_params.user_id) {
        return 'You (click to remove)';
    }
    return people.get_person_from_user_id(user_id).full_name;
}

function generate_title(emoji_name, user_ids) {
    var i = user_ids.indexOf(page_params.user_id);
    if (i !== -1) {
        // Move current user's id to start of list
        user_ids.splice(i, 1);
        user_ids.unshift(page_params.user_id);
    }
    var reacted_with_string = ' reacted with :' + emoji_name + ':';
    var user_names = user_ids.map(full_name);
    if (user_names.length === 1) {
        return user_names[0] + reacted_with_string;
    }
    return _.initial(user_names).join(', ') + ' and ' + _.last(user_names) + reacted_with_string;
}

exports.get_reaction_section = function (message_id) {
    var message_element = $('.message_table').find("[zid='" + message_id + "']");
    var section = message_element.find('.message_reactions');
    return section;
};

exports.find_reaction = function (message_id, emoji_name) {
    var reaction_section = exports.get_reaction_section(message_id);
    var reaction = reaction_section.find("[data-emoji-name='" + emoji_name + "']");
    return reaction;
};

exports.get_add_reaction_button = function (message_id) {
    var reaction_section = exports.get_reaction_section(message_id);
    var add_button = reaction_section.find('.reaction_button');
    return add_button;
};

exports.set_reaction_count = function (reaction, count) {
    var count_element = reaction.find('.message_reaction_count');
    count_element.html(count);
};

exports.add_reaction = function (event) {
    var message_id = event.message_id;
    var emoji_name = event.emoji_name;

    var message = message_store.get(message_id);
    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    event.user.id = event.user.user_id;

    message.reactions.push(event);

    var user_list = get_user_list_for_message_reaction(message, emoji_name);

    if (user_list.length > 1) {
        exports.view.update_existing_reaction({
            message_id: event.message_id,
            emoji_name: event.emoji_name,
            user_list: user_list,
            user_id: event.user.id,
        });
    } else {
        exports.view.insert_new_reaction({
            message_id: event.message_id,
            emoji_name: event.emoji_name,
            user_id: event.user.id,
        });
    }
};

exports.view.update_existing_reaction = function (opts) {
    // Our caller ensures that this message already has a reaction
    // for this emoji and sets up our user_list.  This function
    // simply updates the DOM.

    var message_id = opts.message_id;
    var emoji_name = opts.emoji_name;
    var user_list = opts.user_list;
    var user_id = opts.user_id;

    var reaction = exports.find_reaction(message_id, emoji_name);

    exports.set_reaction_count(reaction, user_list.length);

    var new_title = generate_title(emoji_name, user_list);
    reaction.prop('title', new_title);

    if (user_id === page_params.user_id) {
        reaction.addClass("reacted");
    }
};

exports.view.insert_new_reaction = function (opts) {
    // Our caller ensures we are the first user to react to this
    // message with this emoji, and it populates user_list for
    // us.  We then render the emoji/title/count and insert it
    // before the add button.

    var message_id = opts.message_id;
    var emoji_name = opts.emoji_name;
    var user_id = opts.user_id;
    var user_list = [user_id];

    var context = {
        message_id: message_id,
        emoji_name: emoji_name,
    };

    var new_title = generate_title(emoji_name, user_list);

    if (emoji.active_realm_emojis[emoji_name]) {
        context.is_realm_emoji = true;
        context.url = emoji.active_realm_emojis[emoji_name].emoji_url;
    }

    context.count = 1;
    context.title = new_title;
    context.emoji_alt_code = page_params.emoji_alt_code;
    context.emoji_name_css_class = emoji.emojis_name_to_css_class[emoji_name];

    if (opts.user_id === page_params.user_id) {
        context.class = "message_reaction reacted";
    } else {
        context.class = "message_reaction";
    }

    var new_reaction = $(templates.render('message_reaction', context));

    // Now insert it before the add button.
    var reaction_button_element = exports.get_add_reaction_button(message_id);
    new_reaction.insertBefore(reaction_button_element);
};

exports.remove_reaction = function (event) {
    var emoji_name = event.emoji_name;
    var message_id = event.message_id;
    var user_id = event.user.user_id;
    var i = -1;
    var message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    // Do the data part first:
    // Remove reactions from our message object.
    _.each(message.reactions, function (reaction, index) {
        if (reaction.emoji_name === emoji_name && reaction.user.id === user_id) {
            i = index;
        }
    });

    if (i !== -1) {
        message.reactions.splice(i, 1);
    }

    // Compute the new user list for this reaction.
    var user_list = get_user_list_for_message_reaction(message, emoji_name);

    exports.view.remove_reaction({
        message_id: message_id,
        emoji_name: emoji_name,
        user_list: user_list,
        user_id: user_id,
    });
};

exports.view.remove_reaction = function (opts) {

    var message_id = opts.message_id;
    var emoji_name = opts.emoji_name;
    var user_list = opts.user_list;
    var user_id = opts.user_id;

    var reaction = exports.find_reaction(message_id, emoji_name);

    if (user_list.length === 0) {
        // If this user was the only one reacting for this emoji, we simply
        // remove the reaction and exit.
        reaction.remove();
        return;
    }

    // The emoji still has reactions from other users, so we need to update
    // the title/count and, if the user is the current user, turn off the
    // "reacted" class.

    var new_title = generate_title(emoji_name, user_list);
    reaction.prop('title', new_title);

    exports.set_reaction_count(reaction, user_list.length);

    if (user_id === page_params.user_id) {
        reaction.removeClass("reacted");
    }
};

exports.get_emojis_used_by_user_for_message_id = function (message_id) {
    var user_id = page_params.user_id;
    var message = message_store.get(message_id);
    var reactions_by_user = message.reactions.filter(function (reaction) {
        return reaction.user.id === user_id;
    });
    return reactions_by_user.map(function (reaction) {
        return reaction.emoji_name;
    });
};

exports.get_message_reactions = function (message) {
    var message_reactions = new Dict();
    _.each(message.reactions, function (reaction) {
        var user_id = reaction.user.id;
        if (!people.is_known_user_id(user_id)) {
            blueslip.warn('Unknown user_id ' + user_id +
                          'in reaction for message ' + message.id);
            return;
        }
        reaction.user_ids = [];
        var collapsed_reaction = message_reactions.setdefault(
            reaction.emoji_name,
            _.omit(reaction, 'user')
        );
        collapsed_reaction.user_ids.push(user_id);
    });
    var reactions = message_reactions.items().map(function (item) {
        var reaction = item[1];
        reaction.emoji_name_css_class = reaction.emoji_code;
        reaction.count = reaction.user_ids.length;
        reaction.title = generate_title(reaction.emoji_name, reaction.user_ids);
        reaction.emoji_alt_code = page_params.emoji_alt_code;

        if (reaction.reaction_type !== 'unicode_emoji') {
            reaction.is_realm_emoji = true;
            reaction.url = emoji.all_realm_emojis[reaction.emoji_name].emoji_url;
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

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = reactions;
}
