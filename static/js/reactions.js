var reactions = (function () {
var exports = {};

function send_reaction_ajax(message_id, emoji_name, operation) {
    if (!emoji.emojis_by_name[emoji_name]) {
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

function get_user_list_for_message_reaction(message_id, emoji_name) {
    var message = message_store.get(message_id);
    var matching_reactions = message.reactions.filter(function (reaction) {
        return reaction.emoji_name === emoji_name;
    });
    return matching_reactions.map(function (reaction) {
        return reaction.user.id;
    });
}

exports.message_reaction_on_click = function (message_id, emoji_name) {
    // When a message's reaction is clicked,
    // if the user has reacted to this message with this emoji
    // the reaction is removed
    // otherwise, the reaction is added
    var user_list = get_user_list_for_message_reaction(message_id, emoji_name);
    var operation = 'remove';
    if (user_list.indexOf(page_params.user_id) === -1) {
        // User hasn't reacted with this emoji to this message
        operation = 'add';
    }
    send_reaction_ajax(message_id, emoji_name, operation);
};

exports.toggle_reaction = function (message_id, emoji_name) {
    var user_list = get_user_list_for_message_reaction(message_id, emoji_name);
    var operation = 'add';
    if (user_list.indexOf(page_params.user_id) !== -1) {
        // User has reacted with this emoji to this message
        operation = 'remove';
    }
    send_reaction_ajax(message_id, emoji_name, operation);
    popovers.hide_reactions_popover();
};

function filter_emojis() {
    var elt = $(".reaction-popover-filter").expectOne();
    var search_term = elt.val().trim();
    var reaction_list = $(".reaction-popover-reaction");
    if (search_term !== '') {
        reaction_list.filter(function () {
            return this.title.indexOf(search_term) === -1;
        }).css("display", "none");
        reaction_list.filter(function () {
            return this.title.indexOf(search_term) !== -1;
        }).css("display", "block");
    } else {
        reaction_list.css("display", "block");
    }
}

function maybe_select_emoji(e) {
    var reaction_list = $(".reaction-popover-reaction");
    if (e.keyCode === 13) {
        e.preventDefault();
        var reaction_show_list = reaction_list.filter(function () {
            return this.style.display === "block";
        });
        if (reaction_show_list.length) {
            $(".reaction-popover-filter").val("");
            exports.toggle_reaction(current_msg_list.selected_id(), reaction_show_list[0].title);
        }
    }
}

$(document).on('click', '.reaction-popover-reaction', function () {
    // When an emoji is clicked in the popover,
    // if the user has reacted to this message with this emoji
    // the reaction is removed
    // otherwise, the reaction is added
    var emoji_name = this.title;
    var message_id = $(this).parent().attr('data-message-id');
    var user_list = get_user_list_for_message_reaction(message_id, emoji_name);
    if (user_list.indexOf(page_params.user_id) !== -1) {
        $(this).removeClass('reacted');
    }
    exports.toggle_reaction(message_id, emoji_name);
});

$(document).on('input', '.reaction-popover-filter', filter_emojis);
$(document).on('keydown', '.reaction-popover-filter', maybe_select_emoji);

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

exports.add_reaction = function (event) {
    event.emoji_name_css_class = emoji.emoji_name_to_css_class(event.emoji_name);
    event.user.id = event.user.user_id;
    var message = message_store.get(event.message_id);
    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }
    message.reactions.push(event);
    var message_element = $('.message_table').find("[zid='" + event.message_id + "']");
    var message_reactions_element = message_element.find('.message_reactions');
    var user_list = get_user_list_for_message_reaction(event.message_id, event.emoji_name);
    var new_title = generate_title(event.emoji_name, user_list);
    if (user_list.length === 1) {
        if (emoji.realm_emojis[event.emoji_name]) {
            event.is_realm_emoji = true;
            event.url = emoji.realm_emojis[event.emoji_name].emoji_url;
        }
        event.count = 1;
        event.title = new_title;
        event.emoji_alt_code = page_params.emoji_alt_code;
        if (event.user.id === page_params.user_id) {
            event.class = "message_reaction reacted";
        } else {
            event.class = "message_reaction";
        }
        var reaction_button_element = message_reactions_element.find('.reaction_button');
        $(templates.render('message_reaction', event)).insertBefore(reaction_button_element);
    } else {
        var reaction = message_reactions_element.find("[data-emoji-name='" + event.emoji_name + "']");
        var count_element = reaction.find('.message_reaction_count');
        count_element.html(user_list.length);
        reaction.prop('title', new_title);
        if (event.user.id === page_params.user_id) {
            reaction.addClass("reacted");
        }
    }
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
    _.each(message.reactions, function (reaction, index) {
        if (reaction.emoji_name === emoji_name && reaction.user.id === user_id) {
            i = index;
        }
    });
    if (i !== -1) {
        message.reactions.splice(i, 1);
    }
    var user_list = get_user_list_for_message_reaction(message_id, emoji_name);
    var new_title = generate_title(emoji_name, user_list);
    var message_element = $('.message_table').find("[zid='" + message_id + "']");
    var message_reactions_element = message_element.find('.message_reactions');
    var matching_reactions = message_reactions_element.find('[data-emoji-name="' + emoji_name + '"]');
    var count_element = matching_reactions.find('.message_reaction_count');
    matching_reactions.prop('title', new_title);
    if (user_id === page_params.user_id) {
        matching_reactions.removeClass("reacted");
    }
    count_element.html(user_list.length);
    if (user_list.length === 0) {
        matching_reactions.remove();
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

        var user_list = message_reactions.setdefault(reaction.emoji_name, []);
        user_list.push(user_id);
    });
    var reactions = message_reactions.items().map(function (item) {
        var emoji_name = item[0];
        var user_ids = item[1];
        var reaction = {
            emoji_name: emoji_name,
            emoji_name_css_class: emoji.emoji_name_to_css_class(emoji_name),
            count: user_ids.length,
            title: generate_title(emoji_name, user_ids),
            emoji_alt_code: page_params.emoji_alt_code,
        };
        if (emoji.realm_emojis[reaction.emoji_name]) {
            reaction.is_realm_emoji = true;
            reaction.url = emoji.realm_emojis[reaction.emoji_name].emoji_url;
        }
        if (get_user_list_for_message_reaction(message.id,
            reaction.emoji_name).indexOf(page_params.user_id) !== -1) {
            reaction.class = "message_reaction reacted";
        } else {
            reaction.class = "message_reaction";
        }
        return reaction;
    });
    return reactions;
};

$(function () {
    $(document).on('message_id_changed', function (event) {
        // When a message ID is changed via editing, update any
        // data-message-id references to it.
        var elts = $(".message_reactions[data-message-id='" + event.old_id + "']");
        elts.attr("data-message-id", event.new_id);
    });
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = reactions;
}
