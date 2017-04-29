var emoji_picker = (function () {

var exports = {};

// We handle both the reactions emoji popover and the
// compose emoji picker with the emoji picker widget
// implemented in this module.
var current_message_reactions_popover_elem;
var emoji_map_is_open = false;
var emoji_map_is_rendered = false;

function render_emoji_popover() {
    var content = (function () {
        var map = {};
        for (var x in emoji.emojis_name_to_css_class) {
            if (!emoji.realm_emojis[x]) {
                map[x] = {
                    name: x,
                    css_name: emoji.emojis_name_to_css_class[x],
                    url: emoji.emojis_by_name[x],
                };
            }
        }

        return templates.render('emoji_popover_content', {
            emoji_list: map,
            realm_emoji: emoji.realm_emojis,
        });
    }());
    $('.emoji_popover').empty();
    $('.emoji_popover').append(content);
}

function promote_popular(a, b) {
    function rank(name) {
        switch (name) {
            case '+1': return 1;
            case 'tada': return 2;
            case 'simple_smile': return 3;
            case 'laughing': return 4;
            case '100': return 5;
            default: return 999;
        }
    }

    var diff = rank(a.name) - rank(b.name);

    if (diff !== 0) {
        return diff;
    }

    return util.strcmp(a.name, b.name);
}

function compute_placement(elt) {
    var approx_popover_height = 400;
    var approx_popover_width = 400;
    var distance_from_bottom = message_viewport.height() - elt.offset().top;
    var distance_from_right = message_viewport.width() - elt.offset().left;
    var will_extend_beyond_bottom_of_viewport = distance_from_bottom < approx_popover_height;
    var will_extend_beyond_top_of_viewport = elt.offset().top < approx_popover_height;
    var will_extend_beyond_left_of_viewport = elt.offset().left < (approx_popover_width / 2);
    var will_extend_beyond_right_of_viewport = distance_from_right < (approx_popover_width / 2);
    var placement = 'bottom';
    if (will_extend_beyond_bottom_of_viewport && !will_extend_beyond_top_of_viewport) {
        placement = 'top';
    }
    if (will_extend_beyond_right_of_viewport && !will_extend_beyond_left_of_viewport) {
        placement = 'left';
    }
    if (will_extend_beyond_left_of_viewport && !will_extend_beyond_right_of_viewport) {
        placement = 'right';
    }
    return placement;
}

function generate_emoji_picker_content(id) {
    var emojis_used = reactions.get_emojis_used_by_user_for_message_id(id);
    var emojis = _.clone(emoji.emojis_name_to_css_class);

    var realm_emojis = emoji.realm_emojis;
    _.each(realm_emojis, function (realm_emoji, realm_emoji_name) {
        emojis[realm_emoji_name] = {
            name: realm_emoji_name,
            is_realm_emoji: true,
            url: realm_emoji.emoji_url,
        };
    });
    _.each(emojis_used, function (emoji_name) {
        emojis[emoji_name] = {
            name: emoji_name,
            has_reacted: true,
            css_class: emoji.emoji_name_to_css_class(emoji_name),
            is_realm_emoji: emojis[emoji_name].is_realm_emoji,
            url: emojis[emoji_name].url,
        };
    });

    var emoji_recs = _.map(emojis, function (val, emoji_name) {
        if (val.name) {
            return val;
        }

        return {
            name: emoji_name,
            css_class: emoji.emoji_name_to_css_class(emoji_name),
            has_reacted: false,
            is_realm_emoji: false,
        };
    });

    var args = {
        message_id: id,
        emojis: emoji_recs.sort(promote_popular),
    };

    return templates.render('reaction_popover_content', args);
}

exports.toggle_reactions_popover = function (element, id) {
    var last_popover_elem = current_message_reactions_popover_elem;
    popovers.hide_all();
    $(element).closest('.message_row').toggleClass('has_popover has_reactions_popover');
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    current_msg_list.select_id(id);
    var elt = $(element);

    if (elt.data('popover') === undefined) {
        elt.prop('title', '');
        elt.popover({
            placement: compute_placement(elt),
            title:     "",
            content:   generate_emoji_picker_content(id),
            trigger:   "manual",
        });
        elt.popover("show");
        elt.prop('title', 'Add reaction...');
        $('.reaction-popover-filter').focus();
        $(".reaction-popover-emoji-map").perfectScrollbar({
            suppressScrollX: true,
            useKeyboard: false,
            wheelSpeed: 25,
        });
        current_message_reactions_popover_elem = elt;
        reactions.render_reaction_show_list();
    }
};

exports.reactions_popped = function () {
    return current_message_reactions_popover_elem !== undefined;
};

exports.hide_reactions_popover = function () {
    $('.has_popover').removeClass('has_popover has_reactions_popover');
    if (exports.reactions_popped()) {
        $(".reaction-popover-emoji-map").perfectScrollbar("destroy");
        current_message_reactions_popover_elem.popover("destroy");
        current_message_reactions_popover_elem = undefined;
    }
};

exports.reset_emoji_popover = function () {
    emoji_map_is_rendered = false;
};

exports.hide_emoji_map_popover = function () {
    if (emoji_map_is_open) {
        $('.emoji_popover').css('display', 'none');
        $('.drag').css('display', 'none');
        $("#new_message_content").focus();
        emoji_map_is_open = false;
    }
};
exports.show_emoji_map_popover = function () {
    if (!emoji_map_is_open) {
        $('.emoji_popover').css('display', 'inline-block');
        $('.emoji_popover').scrollTop(0);
        $('.drag').show();
        $("#new_message_content").focus();
        emoji_map_is_open = true;
    }
};

exports.register_click_handlers = function () {
    $("body").on("click", ".emoji_popover", function (e) {
        e.stopPropagation();
    });

    $(".emoji_popover").on("click", ".emoji", function (e) {
        var emoji_choice = $(e.target).attr("title");
        var textarea = $("#new_message_content");
        textarea.caret(emoji_choice);
        textarea.focus();
        e.stopPropagation();
    });

    $("#compose").on("click", "#emoji_map", function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (emoji_map_is_open) {
            // If the popover is already shown, clicking again should toggle it.
            emoji_picker.hide_emoji_map_popover();
        } else {
            // If the emoji_map is not rendered before then, a call to render_emoji_popover is made.
            if (!emoji_map_is_rendered) {
                render_emoji_popover();
                emoji_map_is_rendered = true;
            }
            emoji_picker.show_emoji_map_popover();
        }
    });

    $("#main_div").on("click", ".reactions_hover, .reaction_button", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        emoji_picker.toggle_reactions_popover(this, rows.id(row));
    });

    $("body").on("click", ".actions_popover .reaction_button", function (e) {
        var msgid = $(e.currentTarget).data('message-id');
        e.preventDefault();
        e.stopPropagation();
        // HACK: Because we need the popover to be based off an
        // element that definitely exists in the page even if the
        // message wasn't sent by us and thus the .reaction_hover
        // element is not present, we use the message's
        // .icon-vector-chevron-down element as the base for the popover.
        emoji_picker.toggle_reactions_popover($(".selected_message .icon-vector-chevron-down")[0], msgid);
    });
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = emoji_picker;
}
