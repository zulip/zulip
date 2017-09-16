var emoji_picker = (function () {

var exports = {};

// Emoji picker is of fixed width and height. Update these
// whenever these values are changed in `reactions.css`.
var APPROX_HEIGHT = 330;
var APPROX_WIDTH = 255;

// The functionalities for reacting to a message with an emoji
// and composing a message with an emoji share a single widget,
// implemented as the emoji_popover.
exports.emoji_collection = {};
exports.complete_emoji_catalog = [];
var current_message_emoji_popover_elem;
var emoji_catalog_last_coordinates = {
    section: 0,
    index: 0,
};
var current_section = 0;
var current_index = 0;
var search_is_active = false;
var search_results = [];
var section_head_offsets = [];

function get_rendered_emoji_categories() {
    if (exports.complete_emoji_catalog.length === 0) {
        blueslip.error('emoji_picker: Emoji catalog empty');
        return;
    }

    var current_emoji_categories = [];
    _.each(exports.complete_emoji_catalog, function (category) {
        current_emoji_categories.push({
            name: category.name,
            icon: category.icon,
        });
    });
    return current_emoji_categories;
}

function get_all_emoji_categories() {
    return [
        { name: "Popular", icon: "fa-thumbs-o-up" },
        { name: "People", icon: "fa-smile-o" },
        { name: "Nature", icon: "fa-leaf" },
        { name: "Foods", icon: "fa-cutlery" },
        { name: "Activity", icon: "fa-soccer-ball-o" },
        { name: "Places", icon: "fa-car" },
        { name: "Objects", icon: "fa-lightbulb-o" },
        { name: "Symbols", icon: "fa-hashtag" },
        { name: "Custom", icon: "fa-cog" },
    ];
}

function get_frequently_used_emojis() {
    return [
        '1f44d',    // thumbs_up
        '1f389',    // party_popper
        '1f642',    // simple_smile
        '2764',     // heart
        '1f6e0',    // hammer_and_wrench
        '1f419',    // octopus
    ];
}

function get_total_sections() {
    if (search_is_active) {
        return 1;
    }
    return exports.complete_emoji_catalog.length;
}

function get_max_index(section) {
    if (search_is_active) {
        return search_results.length;
    } else if (section >= 0 && section < get_total_sections()) {
        return exports.complete_emoji_catalog[section].emojis.length;
    }
}

function show_search_results() {
    $(".emoji-popover-emoji-map").hide();
    $(".emoji-popover-category-tabs").hide();
    $(".emoji-search-results-container").show();
    emoji_catalog_last_coordinates = {
        section: current_section,
        index: current_index,
    };
    current_section = 0;
    current_index = 0;
    search_is_active = true;
}

function show_emoji_catalog() {
    $(".emoji-popover-emoji-map").show();
    $(".emoji-popover-category-tabs").show();
    $(".emoji-search-results-container").hide();
    current_section = emoji_catalog_last_coordinates.section;
    current_index = emoji_catalog_last_coordinates.index;
    search_is_active = false;
}

exports.generate_emoji_picker_data = function (realm_emojis) {
    exports.emoji_collection = {};
    exports.complete_emoji_catalog = {};
    exports.complete_emoji_catalog.Custom = [];
    _.each(realm_emojis, function (realm_emoji, realm_emoji_name) {
        exports.emoji_collection[realm_emoji_name] = {
            name: realm_emoji_name,
            aliases: [realm_emoji_name],
            is_realm_emoji: true,
            url: realm_emoji.emoji_url,
            has_reacted: false,
        };
        exports.complete_emoji_catalog.Custom.push(exports.emoji_collection[realm_emoji_name]);
    });

    _.each(emoji_codes.emoji_catalog, function (codepoints, category) {
        exports.complete_emoji_catalog[category] = [];
        _.each(codepoints, function (codepoint) {
            if (emoji_codes.codepoint_to_name.hasOwnProperty(codepoint)) {
                var emoji_name = emoji_codes.codepoint_to_name[codepoint];
                if (!exports.emoji_collection.hasOwnProperty(emoji_name)) {
                    exports.emoji_collection[emoji_name] = {
                        name: emoji_name,
                        aliases: emoji.default_emoji_aliases[codepoint],
                        is_realm_emoji: false,
                        css_class: codepoint,
                        has_reacted: false,
                    };
                    exports.complete_emoji_catalog[category].push(
                        exports.emoji_collection[emoji_name]
                    );
                }
            }
        });
    });

    exports.complete_emoji_catalog.Popular = [];
    var frequently_used_emojis = get_frequently_used_emojis();
    _.each(frequently_used_emojis, function (codepoint) {
        if (emoji_codes.codepoint_to_name.hasOwnProperty(codepoint)) {
            var emoji_name = emoji_codes.codepoint_to_name[codepoint];
            if (exports.emoji_collection.hasOwnProperty(emoji_name)) {
                exports.complete_emoji_catalog.Popular.push(exports.emoji_collection[emoji_name]);
            }
        }
    });

    var categories = get_all_emoji_categories().filter(function (category) {
        return !!exports.complete_emoji_catalog[category.name];
    });
    exports.complete_emoji_catalog = categories.map(function (category) {
        return {
            name: category.name,
            icon: category.icon,
            emojis: exports.complete_emoji_catalog[category.name],
        };
    });
};

var generate_emoji_picker_content = function (id) {
    var emojis_used = [];

    if (id !== undefined) {
        emojis_used = reactions.get_emojis_used_by_user_for_message_id(id);
    }
    _.each(exports.emoji_collection, function (emoji_dict) {
        emoji_dict.has_reacted = _.any(emoji_dict.aliases, function (alias) {
            return _.contains(emojis_used, alias);
        });
    });

    return templates.render('emoji_popover_content', {
        message_id: id,
        emoji_categories: exports.complete_emoji_catalog,
    });
};

function add_scrollbar(element) {
    $(element).perfectScrollbar({
        suppressScrollX: true,
        useKeyboard: false,
        // Picked so that each mousewheel bump moves 1 emoji down.
        wheelSpeed: 0.68,
    });
}

function refill_section_head_offsets(popover) {
    section_head_offsets = [];
    popover.find('.emoji-popover-subheading').each(function () {
        section_head_offsets.push({
            section: $(this).attr('data-section'),
            position_y: $(this).position().top,
        });
    });
}

exports.reactions_popped = function () {
    return current_message_emoji_popover_elem !== undefined;
};

exports.hide_emoji_popover = function () {
    $('.has_popover').removeClass('has_popover has_emoji_popover');
    if (exports.reactions_popped()) {
        var orig_title = current_message_emoji_popover_elem.data("original-title");
        $(".emoji-popover-emoji-map").perfectScrollbar("destroy");
        $(".emoji-search-results-container").perfectScrollbar("destroy");
        current_message_emoji_popover_elem.popover("destroy");
        current_message_emoji_popover_elem.prop("title", orig_title);
        current_message_emoji_popover_elem.removeClass("reaction_button_visible");
        current_message_emoji_popover_elem = undefined;
    }
};

function get_selected_emoji() {
    return $(".emoji-popover-emoji").filter(":focus")[0];
}

function get_rendered_emoji(section, index) {
    var type = "emoji_picker_emoji";
    if (search_is_active) {
        type = "emoji_search_result";
    }
    var emoji_id = [type, section, index].join("_");
    var emoji = $(".emoji-popover-emoji[data-emoji-id='" + emoji_id + "']");
    if (emoji.length > 0) {
        return emoji;
    }
}

function filter_emojis() {
    var elt = $(".emoji-popover-filter").expectOne();
    var query = elt.val().trim().toLowerCase();
    var message_id = $(".emoji-search-results-container").data("message-id");
    var search_results_visible = $(".emoji-search-results-container").is(":visible");
    if (query !== "") {
        var categories = exports.complete_emoji_catalog;
        var search_terms = query.split(" ");
        search_results = [];
        _.each(categories, function (category) {
            if (category.name === "Popular") {
                return;
            }
            var emojis = category.emojis;
            _.each(emojis, function (emoji_dict) {
                _.any(emoji_dict.aliases, function (alias) {
                    var match = _.every(search_terms, function (search_term) {
                        return alias.indexOf(search_term) >= 0;
                    });
                    if (match) {
                        search_results.push(_.extend({}, emoji_dict, {name: alias}));
                        return true;
                    }
                });
            });
        });
        var search_results_rendered = templates.render('emoji_popover_search_results', {
            search_results: search_results,
            message_id: message_id,
        });
        $('.emoji-search-results').html(search_results_rendered);
        $(".emoji-search-results-container").perfectScrollbar("update");
        if (!search_results_visible) {
            show_search_results();
        }
    } else {
        show_emoji_catalog();
    }
}

function get_alias_to_be_used(message_id, emoji_name) {
    // If the user has reacted to this message, then this function
    // returns the alias of this emoji he used, otherwise, returns
    // the passed name as it is.
    var message = message_store.get(message_id);
    var aliases = [emoji_name];
    if (!emoji.active_realm_emojis.hasOwnProperty(emoji_name)) {
        if (emoji_codes.name_to_codepoint.hasOwnProperty(emoji_name)) {
            var codepoint = emoji_codes.name_to_codepoint[emoji_name];
            aliases = emoji.default_emoji_aliases[codepoint];
        } else {
            blueslip.error("Invalid emoji name.");
            return;
        }
    }
    var user_id = page_params.user_id;
    var reaction = _.find(message.reactions, function (reaction) {
        return (reaction.user.id === user_id) && (_.contains(aliases, reaction.emoji_name));
    });
    if (reaction) {
        return reaction.emoji_name;
    }
    return emoji_name;
}

function toggle_reaction(emoji_name) {
    var message_id = current_msg_list.selected_id();
    var message = message_store.get(message_id);
    if (!message) {
        blueslip.error('reactions: Bad message id: ' + message_id);
        return;
    }

    var alias = get_alias_to_be_used(message_id, emoji_name);
    reactions.toggle_emoji_reaction(message_id, alias);
}

function maybe_select_emoji(e) {
    if (e.keyCode === 13) { // enter key
        e.preventDefault();
        var first_emoji = get_rendered_emoji(0, 0);
        if (first_emoji) {
            if (emoji_picker.is_composition(first_emoji)) {
                first_emoji.click();
            } else {
                toggle_reaction(first_emoji.data("emoji-name"));
            }
        }
    }
}

exports.toggle_selected_emoji = function () {
    // Toggle the currently selected emoji.
    var selected_emoji = get_selected_emoji();

    if (selected_emoji === undefined) {
        return;
    }

    var emoji_name = $(selected_emoji).data("emoji-name");

    toggle_reaction(emoji_name);
};

function round_off_to_previous_multiple(number_to_round, multiple) {
    return (number_to_round - (number_to_round % multiple));
}

function may_be_change_focused_emoji(next_section, next_index) {
    var next_emoji = get_rendered_emoji(next_section, next_index);
    if (next_emoji) {
        current_section = next_section;
        current_index = next_index;
        next_emoji.focus();
        return true;
    }
    return false;
}

function may_be_change_active_section(next_section) {
    if (next_section >= 0 && next_section < get_total_sections()) {
        current_section = next_section;
        current_index = 0;
        var offset = section_head_offsets[current_section];
        if (offset) {
            $(".emoji-popover-emoji-map").scrollTop(offset.position_y);
            may_be_change_focused_emoji(current_section, current_index);
        }
    }
}

function get_next_emoji_coordinates(move_by) {
    var next_section = current_section;
    var next_index = current_index + move_by;
    var max_len;
    if (next_index < 0) {
        next_section = next_section - 1;
        if (next_section >= 0) {
            next_index = get_max_index(next_section) - 1;
            if (move_by === -6) {
                max_len = get_max_index(next_section);
                var prev_multiple = round_off_to_previous_multiple(max_len, 6);
                next_index =  prev_multiple + current_index;
                next_index = next_index >= max_len
                            ? (prev_multiple + current_index - 6)
                            : next_index;
            }
        }
    } else if (next_index >= get_max_index(next_section)) {
        next_section = next_section + 1;
        if (next_section < get_total_sections()) {
            next_index = 0;
            if (move_by === 6) {
                max_len = get_max_index(next_index);
                next_index = current_index % 6;
                next_index = next_index >= max_len ? max_len - 1 : next_index;
            }
        }
    }

    return {
        section: next_section,
        index: next_index,
    };
}

function change_focus_to_filter() {
    $('.emoji-popover-filter').focus();
    // If search is active reset current selected emoji to first emoji.
    if (search_is_active) {
        current_section = 0;
        current_index = 0;
    }
}

exports.navigate = function (event_name) {
    // If search is active and results are empty then return immediately.
    if (search_is_active === true && search_results.length === 0) {
        return;
    }

    var selected_emoji = get_rendered_emoji(current_section, current_index);
    var is_filter_focused = $('.emoji-popover-filter').is(':focus');
    var next_section = 0;
    // special cases
    if (is_filter_focused) {
        // Move down into emoji map.
        var filter_text = $(".emoji-popover-filter").val();
        var is_cursor_at_end = $(".emoji-popover-filter").caret() === filter_text.length;
        if (event_name === "down_arrow" ||
           (is_cursor_at_end && event_name === "right_arrow")) {
            selected_emoji.focus();
            if (current_section === 0 && current_index < 6) {
                $(".emoji-popover-emoji-map").scrollTop(0);
            }
            return true;
        }
        if (event_name === "tab") {
            selected_emoji.focus();
            return true;
        }
        return false;
    } else if ((current_section === 0 && current_index < 6 && event_name === 'up_arrow') ||
               (current_section === 0 && current_index === 0 && event_name === 'left_arrow')) {
        if (selected_emoji) {
            // In this case, we're move up into the reaction
            // filter. Here, we override the default browser
            // behavior, which in Firefox is good (preserving
            // the cursor position) and in Chrome is bad (cursor
            // goes to beginning) with something reasonable and
            // consistent (cursor goes to the end of the filter
            // string).
            $('.emoji-popover-filter').focus().caret(Infinity);
            $(".emoji-popover-emoji-map").scrollTop(0);
            $(".emoji-search-results-container").scrollTop(0);
            current_section = 0;
            current_index = 0;
            return true;
        }
    } else if (event_name === 'tab') {
        change_focus_to_filter();
        return true;
    } else if (event_name === 'shift_tab') {
        if (!is_filter_focused) {
            change_focus_to_filter();
        }
        return true;
    } else if (event_name === 'page_up') {
        next_section = current_section - 1;
        may_be_change_active_section(next_section);
        return true;
    } else if (event_name === 'page_down') {
        next_section = current_section + 1;
        may_be_change_active_section(next_section);
        return true;
    } else if (!is_filter_focused) {
        var next_coord = {};
        switch (event_name) {
            case 'down_arrow':
                next_coord = get_next_emoji_coordinates(6);
                break;
            case 'up_arrow':
                next_coord = get_next_emoji_coordinates(-6);
                break;
            case 'left_arrow':
                next_coord = get_next_emoji_coordinates(-1);
                break;
            case 'right_arrow':
                next_coord = get_next_emoji_coordinates(1);
                break;
        }
        return may_be_change_focused_emoji(next_coord.section, next_coord.index);
    }
    return false;
};

function process_keypress(e) {
    var is_filter_focused = $('.emoji-popover-filter').is(':focus');
    if (!is_filter_focused) {
        var pressed_key = e.which;

        if (pressed_key >= 32 && pressed_key <= 126 || pressed_key === 8) {
            // Handle only printable characters or backspace.
            e.preventDefault();
            e.stopPropagation();

            var emoji_filter = $('.emoji-popover-filter');
            var old_query = emoji_filter.val();
            var new_query = "";

            if (pressed_key === 8) {    // Handles backspace.
                new_query = old_query.slice(0, -1);
            } else {    // Handles any printable character.
                var key_str = String.fromCharCode(e.which);
                new_query = old_query + key_str;
            }

            emoji_filter.val(new_query);
            change_focus_to_filter();
            filter_emojis();
        }
    }
}

exports.emoji_select_tab = function (elt) {
    var scrolltop = elt.scrollTop();
    var scrollheight = elt.prop('scrollHeight');
    var elt_height = elt.height();
    var currently_selected = "";
    section_head_offsets.forEach(function (o) {
        if (scrolltop + elt_height/2 >= o.position_y) {
            currently_selected = o.section;
        }
    });
    // Handles the corner case of the last category being
    // smaller than half of the emoji picker height.
    if (elt_height + scrolltop === scrollheight) {
        currently_selected = section_head_offsets[section_head_offsets.length - 1].section;
    }
    // Handles the corner case of the scrolling back to top.
    if (scrolltop === 0) {
        currently_selected = section_head_offsets[0].section;
    }
    if (currently_selected) {
        $('.emoji-popover-tab-item.active').removeClass('active');
        $('.emoji-popover-tab-item[data-tab-name="'+currently_selected+'"]').addClass('active');
    }
};

function register_popover_events(popover) {
    var $emoji_map = popover.find('.emoji-popover-emoji-map');

    $emoji_map.on("scroll", function () {
        emoji_picker.emoji_select_tab($emoji_map);
    });

    $('.emoji-popover-filter').on('input', filter_emojis);
    $('.emoji-popover-filter').keydown(maybe_select_emoji);
    $('.emoji-popover').keypress(process_keypress);
    $('.emoji-popover').keydown(function (e) {
        // Because of cross-browser issues we need to handle backspace
        // key separately. Firefox fires `keypress` event for backspace
        // key but chrome doesn't so we need to trigger the logic for
        // handling backspace in `keydown` event which is fired by both.
        if (e.which === 8) {
            process_keypress(e);
        }
    });
}

exports.render_emoji_popover = function (elt, id) {
    var template_args = {
        class: "emoji-info-popover",
        categories: get_rendered_emoji_categories(),
    };
    var placement = popovers.compute_placement(elt, APPROX_HEIGHT, APPROX_WIDTH, true);
    elt.popover({
        // temporary patch for handling popover placement of `viewport_center`
        placement: placement === 'viewport_center' ? 'left' : placement,
        template:  templates.render('emoji_popover', template_args),
        title:     "",
        content:   generate_emoji_picker_content(id),
        trigger:   "manual",
    });
    elt.popover("show");
    elt.prop("title", i18n.t("Add emoji reaction (:)"));
    $('.emoji-popover-filter').focus();
    add_scrollbar($(".emoji-popover-emoji-map"));
    add_scrollbar($(".emoji-search-results-container"));
    current_message_emoji_popover_elem = elt;

    emoji_catalog_last_coordinates = {
        section: 0,
        index: 0,
    };
    show_emoji_catalog();

    var popover = elt.data('popover').$tip;
    refill_section_head_offsets(popover);
    register_popover_events(popover);
};

exports.toggle_emoji_popover = function (element, id) {
    var last_popover_elem = current_message_emoji_popover_elem;
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    $(element).closest('.message_row').toggleClass('has_popover has_emoji_popover');
    var elt = $(element);
    if (id !== undefined) {
        current_msg_list.select_id(id);
    }

    if (elt.data('popover') === undefined) {
        // Keep the element over which the popover is based off visible.
        elt.addClass("reaction_button_visible");
        emoji_picker.render_emoji_popover(elt, id);
    }
};

exports.register_click_handlers = function () {

    $(document).on('click', '.emoji-popover-emoji.reaction', function () {
        // When an emoji is clicked in the popover,
        // if the user has reacted to this message with this emoji
        // the reaction is removed
        // otherwise, the reaction is added
        var emoji_name = $(this).data("emoji-name");
        toggle_reaction(emoji_name);
    });

    $(document).on('click', '.emoji-popover-emoji.composition', function (e) {
        var emoji_name = $(this).data("emoji-name");
        var emoji_text = ':' + emoji_name + ':';
        var textarea = $("#new_message_content");
        textarea.caret(emoji_text);
        textarea.focus();
        e.stopPropagation();
        emoji_picker.hide_emoji_popover();
    });

    $("#compose").on("click", "#emoji_map", function (e) {
        e.preventDefault();
        e.stopPropagation();
        emoji_picker.toggle_emoji_popover(this);
    });

    $("#main_div").on("click", ".reaction_button", function (e) {
        e.stopPropagation();

        var message_id = rows.get_message_id(this);
        emoji_picker.toggle_emoji_popover(this, message_id);
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
        var elem = $(".selected_message .actions_hover")[0];
        emoji_picker.toggle_emoji_popover(elem, msgid);
    });

    $("body").on("click", ".emoji-popover-tab-item", function (e) {
        e.stopPropagation();
        e.preventDefault();
        var offset = _.find(section_head_offsets, function (o) {
            return o.section === $(this).attr("data-tab-name");
        }.bind(this));

        if (offset) {
            $(".emoji-popover-emoji-map").scrollTop(offset.position_y);
        }
    });
};

exports.is_composition = function (emoji) {
    return $(emoji).hasClass('composition');
};

exports.initialize = function () {
    exports.generate_emoji_picker_data(emoji.active_realm_emojis);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = emoji_picker;
}
