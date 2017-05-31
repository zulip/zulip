var emoji_picker = (function () {

var exports = {};

// The functionalities for reacting to a message with an emoji
// and composing a message with an emoji share a single widget,
// implemented as the emoji_popover.
var current_message_emoji_popover_elem;
var emoji_collection = {};
var complete_emoji_catalog = {};
var rendered_emoji_map = [];
var emoji_catalog_last_coordinates = {
    section: 0,
    index: 0,
};
var current_section = 0;
var current_index = 0;

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

function populate_rendered_emoji_map() {
    var collections = $(".emoji-collection");
    rendered_emoji_map = [];
    _.each(collections, function (collection) {
        rendered_emoji_map.push($(collection).children().toArray());
    });
}

function get_emoji_categories() {
    return [
        { name: "People", icon: "fa-smile-o" },
        { name: "Nature", icon: "fa-leaf" },
        { name: "Foods", icon: "fa-cutlery" },
        { name: "Activity", icon: "fa-soccer-ball-o" },
        { name: "Places", icon: "fa-car" },
        { name: "Objects", icon: "fa-lightbulb-o" },
        { name: "Symbols", icon: "fa-hashtag" },
        { name: "Custom", icon: "fa-thumbs-o-up" },
    ];
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
}

function show_emoji_catalog() {
    $(".emoji-popover-emoji-map").show();
    $(".emoji-popover-category-tabs").show();
    $(".emoji-search-results-container").hide();
    current_section = emoji_catalog_last_coordinates.section;
    current_index = emoji_catalog_last_coordinates.index;
}

exports.generate_emoji_picker_data = function (realm_emojis) {
    var emoji_by_unicode = (function () {
        var map = {};

        _.each(emoji.emojis, function (emoji) {
            map[emoji.codepoint] = emoji;
        });

        return {
            find: function (unicode) {
                return map[unicode];
            },
        };
    }());
    _.each(emoji_codes.emoji_catalog, function (emoji_codes, category) {
        complete_emoji_catalog[category] = [];
        _.each(emoji_codes, function (emoji_code) {
            var _emoji = emoji_by_unicode.find(emoji_code);
            if (_emoji !== undefined) {
                var emoji_name = _emoji.emoji_name;
                emoji_collection[emoji_name] = {
                    name: emoji_name,
                    is_realm_emoji: false,
                    css_class: emoji_code,
                    has_reacted: false,
                };
                complete_emoji_catalog[category].push(emoji_collection[emoji_name]);
            }
        });
    });
    complete_emoji_catalog.Custom = [];
    _.each(realm_emojis, function (realm_emoji, realm_emoji_name) {
        emoji_collection[realm_emoji_name] = {
            name: realm_emoji_name,
            is_realm_emoji: true,
            url: realm_emoji.emoji_url,
            has_reacted: false,
        };
        complete_emoji_catalog.Custom.push(emoji_collection[realm_emoji_name]);
    });

    var categories = get_emoji_categories();
    complete_emoji_catalog = categories.map(function (category) {
        if (complete_emoji_catalog[category.name] !== undefined) {
            return Object.assign(category, {emojis: complete_emoji_catalog[category.name]});
        }
        return null;
    });
};

var subhead_offsets = [];

var generate_emoji_picker_content = function (id) {
    var emojis_used = [];

    if (id !== undefined) {
        emojis_used = reactions.get_emojis_used_by_user_for_message_id(id);
    }
    _.each(emoji_collection, function (emoji_dict) {
        emoji_dict.has_reacted = _.contains(emojis_used, emoji_dict.name);
    });

    return templates.render('emoji_popover_content', {
        message_id: id,
        emoji_categories: complete_emoji_catalog,
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
        elt.prop('title', '');
        var template_args = {
            class: "emoji-info-popover",
            categories: get_emoji_categories(),
        };
        elt.popover({
            placement: compute_placement(elt),
            template:  templates.render('emoji_popover', template_args),
            title:     "",
            content:   generate_emoji_picker_content(id),
            trigger:   "manual",
        });
        elt.popover("show");
        elt.prop('title', 'Add reaction...');
        $('.emoji-popover-filter').focus();
        add_scrollbar($(".emoji-popover-emoji-map"));
        add_scrollbar($(".emoji-search-results-container"));
        current_message_emoji_popover_elem = elt;

        emoji_catalog_last_coordinates = {
            section: 0,
            index: 0,
        };
        populate_rendered_emoji_map();
        show_emoji_catalog();

        $('.emoji-popover-subheading').each(function () {
            subhead_offsets.push({
                section: $(this).attr('data-section'),
                position_y: $(this).position().top,
            });
        });
        var $emoji_map = $('.emoji-popover-emoji-map');
        $emoji_map.on("scroll", function () {
            emoji_picker.emoji_select_tab($emoji_map);
        });
    }
};

exports.reactions_popped = function () {
    return current_message_emoji_popover_elem !== undefined;
};

exports.hide_emoji_popover = function () {
    $('.has_popover').removeClass('has_popover has_emoji_popover');
    if (exports.reactions_popped()) {
        $(".emoji-popover-emoji-map").perfectScrollbar("destroy");
        $(".emoji-search-results-container").perfectScrollbar("destroy");
        current_message_emoji_popover_elem.popover("destroy");
        current_message_emoji_popover_elem = undefined;
    }
};

function get_selected_emoji() {
    return $(".emoji-popover-emoji").filter(":focus")[0];
}

function get_rendered_emoji(section, index) {
    if (section < 0 || index < 0) {
        return;
    }
    if (section < rendered_emoji_map.length) {
        if (index < rendered_emoji_map[section].length) {
            return rendered_emoji_map[section][index];
        }
    }
}

function sort_search_results(search_results, search_term) {
    // Alphabetically sort search results.
    var result = [];
    search_results.sort();
    if (search_term !== '') {
        // After sorting results alphabetically, sort them according to search query.
        result = util.prefix_sort(search_term, search_results);
        result = result.matches.concat(result.rest);
    }
    return result;
}

function filter_emojis() {
    var elt = $(".emoji-popover-filter").expectOne();
    var search_term = elt.val().trim().toLowerCase();
    var message_id = $(".emoji-search-results-container").data("message-id");
    var search_results_visible = $(".emoji-search-results-container").is(":visible");
    if (search_term !== '') {
        var search_results = [];
        _.each(emoji_collection, function (emoji_dict, emoji_name) {
            if (emoji_name.indexOf(search_term) !== -1) {
                search_results.push(emoji_name);
            }
        });
        search_results = sort_search_results(search_results, search_term);
        var result = [];
        _.each(search_results, function (emoji_name) {
            result.push(emoji_collection[emoji_name]);
        });
        var search_results_rendered = templates.render('emoji_popover_search_results', {
            search_results: result,
            message_id: message_id,
        });
        $('.emoji-search-results').html(search_results_rendered);
        if (!search_results_visible) {
            show_search_results();
        }
        rendered_emoji_map = [];
        rendered_emoji_map.push($(".emoji-search-results").children().toArray());
    } else {
        show_emoji_catalog();
        populate_rendered_emoji_map();
    }
}

function maybe_select_emoji(e) {
    if (e.keyCode === 13) { // enter key
        e.preventDefault();
        var first_emoji = get_rendered_emoji(0, 0);
        if (first_emoji) {
            if (emoji_picker.is_composition(first_emoji)) {
                first_emoji.click();
            } else {
                reactions.toggle_emoji_reaction(current_msg_list.selected_id(), first_emoji.title);
            }
        }
    }
}

$(document).on('click', '.emoji-popover-emoji.reaction', function () {
    // When an emoji is clicked in the popover,
    // if the user has reacted to this message with this emoji
    // the reaction is removed
    // otherwise, the reaction is added
    var emoji_name = this.title;
    var message_id = $(this).parent().parent().attr('data-message-id');

    var message = message_store.get(message_id);
    if (!message) {
        blueslip.error('reactions: Bad message id: ' + message_id);
        return;
    }

    if (reactions.current_user_has_reacted_to_emoji(message, emoji_name)) {
        $(this).removeClass('reacted');
    }
    reactions.toggle_emoji_reaction(message_id, emoji_name);
});

exports.toggle_selected_emoji = function () {
    // Toggle the currently selected emoji.
    var message_id = current_msg_list.selected_id();

    var message = message_store.get(message_id);

    if (!message) {
        blueslip.error('reactions: Bad message id: ' + message_id);
        return;
    }

    var selected_emoji = get_selected_emoji();

    if (selected_emoji === undefined) {
        return;
    }

    var emoji_name = selected_emoji.title;

    reactions.toggle_emoji_reaction(message_id, emoji_name);
};

function round_off_to_previous_multiple(number_to_round, multiple) {
    return (number_to_round - (number_to_round % multiple));
}

function get_next_emoji_coordinates(move_by) {
    var next_section = current_section;
    var next_index = current_index + move_by;
    var max_len;
    if (next_index < 0) {
        next_section = next_section - 1;
        if (next_section >= 0) {
            next_index = rendered_emoji_map[next_section].length - 1;
            if (move_by === -6) {
                max_len = rendered_emoji_map[next_section].length;
                var prev_multiple = round_off_to_previous_multiple(max_len, 6);
                next_index =  prev_multiple + current_index;
                next_index = next_index >= max_len ? max_len - 1 : next_index;
            }
        }
    } else if (next_index >= rendered_emoji_map[next_section].length) {
        next_section = next_section + 1;
        if (next_section < rendered_emoji_map.length) {
            next_index = 0;
            if (move_by === 6) {
                max_len = rendered_emoji_map[next_section].length;
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

exports.navigate = function (e, event_name) {
    var selected_emoji = get_rendered_emoji(current_section, current_index);
    // special cases
    if (event_name === 'down_arrow') {
        var is_filter_focused = $('.emoji-popover-filter').is(':focus');
        if (is_filter_focused && current_section === 0 && current_index === 0) {
            // move down into emoji map
            $(selected_emoji).focus();
            $(".emoji-popover-emoji-map").scrollTop(0);
            return true;
        }
    } else if (event_name === 'up_arrow') {
        if (selected_emoji && current_section === 0 && current_index < 6) {
            // In this case, we're move up into the reaction filter
            // rows.  Here, we override the default browser behavior,
            // which in Firefox is good (preserving the cursor
            // position) and in Chrome is bad (cursor goes to
            // beginning) with something reasonable and consistent
            // (cursor goes to the end of the filter string).
            $('.emoji-popover-filter').focus().caret(Infinity);
            $(".emoji-popover-emoji-map").scrollTop(0);
            return true;
        }
    } else if (event_name === 'tab') {
        if ($('.emoji-popover-filter').is(':focus')) {
            selected_emoji.focus();
        } else {
            $('.emoji-popover-filter').focus();
        }
        return true;
    }

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
    var next_emoji = get_rendered_emoji(next_coord.section, next_coord.index);
    if (next_emoji) {
        current_section = next_coord.section;
        current_index = next_coord.index;
        $(next_emoji).focus();
        return true;
    }
    return false;
};

exports.emoji_select_tab = function (elt) {
    var scrolltop = elt.scrollTop();
    var scrollheight = elt.prop('scrollHeight');
    var elt_height = elt.height();
    var currently_selected = "";
    subhead_offsets.forEach(function (o) {
        if (scrolltop + elt_height/2 >= o.position_y) {
            currently_selected = o.section;
        }
    });
    // Handles the corner case of the last category being
    // smaller than half of the emoji picker height.
    if (elt_height + scrolltop === scrollheight) {
        currently_selected = subhead_offsets[subhead_offsets.length - 1].section;
    }
    if (currently_selected) {
        $('.emoji-popover-tab-item.active').removeClass('active');
        $('.emoji-popover-tab-item[data-tab-name="'+currently_selected+'"]').addClass('active');
    }
};

exports.register_click_handlers = function () {

    $(document).on('click', '.emoji-popover-emoji.composition', function (e) {
        var emoji_text = ':' + this.title + ':';
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

    $("#main_div").on("click", ".reactions_hover, .reaction_button", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        emoji_picker.toggle_emoji_popover(this, rows.id(row));
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
        emoji_picker.toggle_emoji_popover($(".selected_message .icon-vector-chevron-down")[0], msgid);
    });

    $(document).on('input', '.emoji-popover-filter', filter_emojis);
    $(document).on('keydown', '.emoji-popover-filter', maybe_select_emoji);

    $("body").on("click", ".emoji-popover-tab-item", function () {
        var offset = _.find(subhead_offsets, function (o) {
            return o.section === $(this).attr("data-tab-name");
        }.bind(this));

        if (offset) {
            $(".emoji-popover-emoji-map").scrollTop(offset.position_y);
        }
    });
};

exports.is_composition = function (emoji) {
    return emoji.classList.contains('composition');
};

(function initialize() {
    exports.generate_emoji_picker_data(emoji.realm_emojis);
}());

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = emoji_picker;
}
