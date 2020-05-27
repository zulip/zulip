const emoji_codes = require("../generated/emoji/emoji_codes.json");
const typeahead = require("../shared/js/typeahead");

const render_emoji_popover = require('../templates/emoji_popover.hbs');
const render_emoji_popover_content = require('../templates/emoji_popover_content.hbs');
const render_emoji_popover_search_results = require('../templates/emoji_popover_search_results.hbs');
const render_emoji_showcase = require("../templates/emoji_showcase.hbs");

// Emoji picker is of fixed width and height. Update these
// whenever these values are changed in `reactions.css`.
const APPROX_HEIGHT = 375;
const APPROX_WIDTH = 255;

// The functionalities for reacting to a message with an emoji
// and composing a message with an emoji share a single widget,
// implemented as the emoji_popover.
exports.complete_emoji_catalog = [];

let current_message_emoji_popover_elem;
let emoji_catalog_last_coordinates = {
    section: 0,
    index: 0,
};
let current_section = 0;
let current_index = 0;
let search_is_active = false;
const search_results = [];
let section_head_offsets = [];
let edit_message_id = null;

function get_all_emoji_categories() {
    return [
        { name: "Popular", icon: "fa-star-o" },
        { name: "Smileys & Emotion", icon: "fa-smile-o" },
        { name: "People & Body", icon: "fa-thumbs-o-up" },
        { name: "Animals & Nature", icon: "fa-leaf" },
        { name: "Food & Drink", icon: "fa-cutlery" },
        { name: "Activities", icon: "fa-soccer-ball-o" },
        { name: "Travel & Places", icon: "fa-car" },
        { name: "Objects", icon: "fa-lightbulb-o" },
        { name: "Symbols", icon: "fa-hashtag" },
        { name: "Custom", icon: "fa-cog" },
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

function get_emoji_id(section, index) {
    let type = "emoji_picker_emoji";
    if (search_is_active) {
        type = "emoji_search_result";
    }
    const emoji_id = [type, section, index].join(",");
    return emoji_id;
}

function get_emoji_coordinates(emoji_id) {
    // Emoji id is of the following form:
    //    <emoji_type>_<section_number>_<index>.
    // See `get_emoji_id()`.
    const emoji_info = emoji_id.split(",");
    return {
        section: parseInt(emoji_info[1], 10),
        index: parseInt(emoji_info[2], 10),
    };
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
    const catalog = new Map();
    catalog.set("Custom", Array.from(realm_emojis.keys(), realm_emoji_name =>
        emoji.emojis_by_name.get(realm_emoji_name)
    ));

    for (const [category, codepoints] of Object.entries(emoji_codes.emoji_catalog)) {
        const emojis = [];
        for (const codepoint of codepoints) {
            const name = emoji.get_emoji_name(codepoint);
            if (name !== undefined) {
                const emoji_dict = emoji.emojis_by_name.get(name);
                if (emoji_dict !== undefined && emoji_dict.is_realm_emoji !== true) {
                    emojis.push(emoji_dict);
                }
            }
        }
        catalog.set(category, emojis);
    }

    const popular = [];
    for (const codepoint of typeahead.popular_emojis) {
        const name = emoji.get_emoji_name(codepoint);
        if (name !== undefined) {
            const emoji_dict = emoji.emojis_by_name.get(name);
            if (emoji_dict !== undefined) {
                popular.push(emoji_dict);
            }
        }
    }
    catalog.set("Popular", popular);

    const categories = get_all_emoji_categories().filter(category => catalog.has(category.name));
    exports.complete_emoji_catalog = categories.map(category => ({
        name: category.name,
        icon: category.icon,
        emojis: catalog.get(category.name),
    }));
};

const generate_emoji_picker_content = function (id) {
    let emojis_used = [];

    if (id !== undefined) {
        emojis_used = reactions.get_emojis_used_by_user_for_message_id(id);
    }
    for (const emoji_dict of emoji.emojis_by_name.values()) {
        emoji_dict.has_reacted = emoji_dict.aliases.some(alias => emojis_used.includes(alias));
    }

    return render_emoji_popover_content({
        message_id: id,
        emoji_categories: exports.complete_emoji_catalog,
    });
};

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
        const orig_title = current_message_emoji_popover_elem.data("original-title");
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
    const emoji_id = get_emoji_id(section, index);
    const emoji = $(".emoji-popover-emoji[data-emoji-id='" + emoji_id + "']");
    if (emoji.length > 0) {
        return emoji;
    }
}

function filter_emojis() {
    const elt = $(".emoji-popover-filter").expectOne();
    const query = elt.val().trim().toLowerCase();
    const message_id = $(".emoji-search-results-container").data("message-id");
    const search_results_visible = $(".emoji-search-results-container").is(":visible");
    if (query !== "") {
        const categories = exports.complete_emoji_catalog;
        const search_terms = query.split(" ");
        search_results.length = 0;

        for (const category of categories) {
            if (category.name === "Popular") {
                continue;
            }
            const emojis = category.emojis;

            for (const emoji_dict of emojis) {
                for (const alias of emoji_dict.aliases) {
                    const match = search_terms.every(search_term => alias.includes(search_term));
                    if (match) {
                        search_results.push({ ...emoji_dict, name: alias });
                        break;  // We only need the first matching alias per emoji.
                    }
                }
            }
        }

        const rendered_search_results = render_emoji_popover_search_results({
            search_results: search_results,
            message_id: message_id,
        });
        $('.emoji-search-results').html(rendered_search_results);
        ui.reset_scrollbar($(".emoji-search-results-container"));
        if (!search_results_visible) {
            show_search_results();
        }
    } else {
        show_emoji_catalog();
    }
}

function toggle_reaction(emoji_name) {
    const message_id = current_msg_list.selected_id();
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error('reactions: Bad message id: ' + message_id);
        return;
    }

    reactions.toggle_emoji_reaction(message_id, emoji_name);
}

function maybe_select_emoji(e) {
    if (e.keyCode === 13) { // enter key
        e.preventDefault();
        const first_emoji = get_rendered_emoji(0, 0);
        if (first_emoji) {
            if (exports.is_composition(first_emoji)) {
                first_emoji.click();
            } else {
                toggle_reaction(first_emoji.attr("data-emoji-name"));
            }
        }
    }
}

exports.toggle_selected_emoji = function () {
    // Toggle the currently selected emoji.
    const selected_emoji = get_selected_emoji();

    if (selected_emoji === undefined) {
        return;
    }

    const emoji_name = $(selected_emoji).attr("data-emoji-name");

    toggle_reaction(emoji_name);
};

function round_off_to_previous_multiple(number_to_round, multiple) {
    return number_to_round - number_to_round % multiple;
}

function reset_emoji_showcase() {
    $(".emoji-showcase-container").html("");
}

function update_emoji_showcase($focused_emoji) {
    // Don't use jQuery's data() function here. It has the side-effect
    // of converting emoji names like :100:, :1234: etc to number.
    const focused_emoji_name = $focused_emoji.attr("data-emoji-name");
    const canonical_name = emoji.get_canonical_name(focused_emoji_name);
    const focused_emoji_dict = emoji.emojis_by_name.get(canonical_name);

    const emoji_dict = {
        ...focused_emoji_dict,
        name: focused_emoji_name.replace(/_/g, ' '),
    };
    const rendered_showcase = render_emoji_showcase({
        emoji_dict: emoji_dict,
    });

    $(".emoji-showcase-container").html(rendered_showcase);
}

function may_be_change_focused_emoji(next_section, next_index, preserve_scroll) {
    const next_emoji = get_rendered_emoji(next_section, next_index);
    if (next_emoji) {
        current_section = next_section;
        current_index = next_index;
        if (!preserve_scroll) {
            next_emoji.focus();
        } else {
            const $emoji_map = $(".emoji-popover-emoji-map");
            const start = ui.get_scroll_element($emoji_map).scrollTop();
            next_emoji.focus();
            if (ui.get_scroll_element($emoji_map).scrollTop() !== start) {
                ui.get_scroll_element($emoji_map).scrollTop(start);
            }
        }
        update_emoji_showcase(next_emoji);
        return true;
    }
    return false;
}

function may_be_change_active_section(next_section) {
    if (next_section >= 0 && next_section < get_total_sections()) {
        current_section = next_section;
        current_index = 0;
        const offset = section_head_offsets[current_section];
        if (offset) {
            ui.get_scroll_element($(".emoji-popover-emoji-map")).scrollTop(offset.position_y);
            may_be_change_focused_emoji(current_section, current_index);
        }
    }
}

function get_next_emoji_coordinates(move_by) {
    let next_section = current_section;
    let next_index = current_index + move_by;
    let max_len;
    if (next_index < 0) {
        next_section = next_section - 1;
        if (next_section >= 0) {
            next_index = get_max_index(next_section) - 1;
            if (move_by === -6) {
                max_len = get_max_index(next_section);
                const prev_multiple = round_off_to_previous_multiple(max_len, 6);
                next_index =  prev_multiple + current_index;
                next_index = next_index >= max_len
                    ? prev_multiple + current_index - 6
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
    reset_emoji_showcase();
}

exports.navigate = function (event_name) {
    if (event_name === 'toggle_reactions_popover' && exports.reactions_popped() &&
        (search_is_active === false || search_results.length === 0)) {
        exports.hide_emoji_popover();
        return true;
    }

    // If search is active and results are empty then return immediately.
    if (search_is_active === true && search_results.length === 0) {
        return;
    }

    const selected_emoji = get_rendered_emoji(current_section, current_index);
    const is_filter_focused = $('.emoji-popover-filter').is(':focus');
    let next_section = 0;
    // special cases
    if (is_filter_focused) {
        // Move down into emoji map.
        const filter_text = $(".emoji-popover-filter").val();
        const is_cursor_at_end = $(".emoji-popover-filter").caret() === filter_text.length;
        if (event_name === "down_arrow" ||
           is_cursor_at_end && event_name === "right_arrow") {
            selected_emoji.focus();
            if (current_section === 0 && current_index < 6) {
                ui.get_scroll_element($(".emoji-popover-emoji-map")).scrollTop(0);
            }
            update_emoji_showcase(selected_emoji);
            return true;
        }
        if (event_name === "tab") {
            selected_emoji.focus();
            update_emoji_showcase(selected_emoji);
            return true;
        }
        return false;
    } else if (current_section === 0 && current_index < 6 && event_name === 'up_arrow' ||
               current_section === 0 && current_index === 0 && event_name === 'left_arrow') {
        if (selected_emoji) {
            // In this case, we're move up into the reaction
            // filter. Here, we override the default browser
            // behavior, which in Firefox is good (preserving
            // the cursor position) and in Chrome is bad (cursor
            // goes to beginning) with something reasonable and
            // consistent (cursor goes to the end of the filter
            // string).
            $('.emoji-popover-filter').focus().caret(Infinity);
            ui.get_scroll_element($(".emoji-popover-emoji-map")).scrollTop(0);
            ui.get_scroll_element($(".emoji-search-results-container")).scrollTop(0);
            current_section = 0;
            current_index = 0;
            reset_emoji_showcase();
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
        let next_coord = {};
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
    const is_filter_focused = $('.emoji-popover-filter').is(':focus');
    const pressed_key = e.which;
    if (!is_filter_focused && pressed_key !== 58) {
        // ':' => 58, is a hotkey for toggling reactions popover.
        if (pressed_key >= 32 && pressed_key <= 126 || pressed_key === 8) {
            // Handle only printable characters or backspace.
            e.preventDefault();
            e.stopPropagation();

            const emoji_filter = $('.emoji-popover-filter');
            const old_query = emoji_filter.val();
            let new_query = "";

            if (pressed_key === 8) {    // Handles backspace.
                new_query = old_query.slice(0, -1);
            } else {    // Handles any printable character.
                const key_str = String.fromCharCode(e.which);
                new_query = old_query + key_str;
            }

            emoji_filter.val(new_query);
            change_focus_to_filter();
            filter_emojis();
        }
    }
}

exports.emoji_select_tab = function (elt) {
    const scrolltop = elt.scrollTop();
    const scrollheight = elt.prop('scrollHeight');
    const elt_height = elt.height();
    let currently_selected = "";
    section_head_offsets.forEach(function (o) {
        if (scrolltop + elt_height / 2 >= o.position_y) {
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
        $('.emoji-popover-tab-item[data-tab-name="' + currently_selected + '"]').addClass('active');
    }
};

function register_popover_events(popover) {
    const $emoji_map = popover.find('.emoji-popover-emoji-map');

    ui.get_scroll_element($emoji_map).on("scroll", function () {
        exports.emoji_select_tab(ui.get_scroll_element($emoji_map));
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
    const template_args = {
        class: "emoji-info-popover",
    };
    let placement = popovers.compute_placement(elt, APPROX_HEIGHT, APPROX_WIDTH, true);

    if (placement === 'viewport_center') {
        // For legacy reasons `compute_placement` actually can
        // return `viewport_center`, but bootstrap doesn't actually
        // support that.
        placement = 'left';
    }

    let template = render_emoji_popover(template_args);

    // if the window is mobile sized, add the `.popover-flex` wrapper to the emoji
    // popover so that it will be wrapped in flex and centered in the screen.
    if (window.innerWidth <= 768) {
        template = "<div class='popover-flex'>" + template + "</div>";
    }

    elt.popover({
        // temporary patch for handling popover placement of `viewport_center`
        placement: placement,
        fix_positions: true,
        template: template,
        title: "",
        content: generate_emoji_picker_content(id),
        html: true,
        trigger: "manual",
    });
    elt.popover("show");
    elt.prop("title", i18n.t("Add emoji reaction (:)"));

    const popover = elt.data('popover').$tip;
    popover.find('.emoji-popover-filter').focus();
    current_message_emoji_popover_elem = elt;

    emoji_catalog_last_coordinates = {
        section: 0,
        index: 0,
    };
    show_emoji_catalog();

    refill_section_head_offsets(popover);
    register_popover_events(popover);
};

exports.toggle_emoji_popover = function (element, id) {
    const last_popover_elem = current_message_emoji_popover_elem;
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    $(element).closest('.message_row').toggleClass('has_popover has_emoji_popover');
    const elt = $(element);
    if (id !== undefined) {
        current_msg_list.select_id(id);
    }

    if (elt.data('popover') === undefined) {
        // Keep the element over which the popover is based off visible.
        elt.addClass("reaction_button_visible");
        exports.render_emoji_popover(elt, id);
    }
    reset_emoji_showcase();
};

exports.register_click_handlers = function () {

    $(document).on('click', '.emoji-popover-emoji.reaction', function () {
        // When an emoji is clicked in the popover,
        // if the user has reacted to this message with this emoji
        // the reaction is removed
        // otherwise, the reaction is added
        const emoji_name = $(this).attr("data-emoji-name");
        toggle_reaction(emoji_name);
    });

    $(document).on('click', '.emoji-popover-emoji.composition', function (e) {
        const emoji_name = $(this).attr("data-emoji-name");
        const emoji_text = ':' + emoji_name + ':';
        // The following check will return false if emoji was not selected in
        // message edit form.
        if (edit_message_id !== null) {
            const edit_message_textarea = $("#message_edit_content_" + edit_message_id);
            // Assign null to edit_message_id so that the selection of emoji in new
            // message composition form works correctly.
            edit_message_id = null;
            compose_ui.insert_syntax_and_focus(emoji_text, edit_message_textarea);
        } else {
            compose_ui.insert_syntax_and_focus(emoji_text);
        }
        e.stopPropagation();
        exports.hide_emoji_popover();
    });

    $("body").on("click", "#emoji_map", function (e) {
        e.preventDefault();
        e.stopPropagation();
        // The data-message-id attribute is only present in the emoji icon present in
        // the message edit form. So the following check will return false if this
        // event was not fired from message edit form.
        if ($(this).attr("data-message-id") !== undefined) {
            // Store data-message-id value in global variable edit_message_id so that
            // its value can be further used to correctly find the message textarea element.
            edit_message_id = $(this).attr("data-message-id");
        } else {
            edit_message_id = null;
        }
        exports.toggle_emoji_popover(this);
    });

    $("#main_div").on("click", ".reaction_button", function (e) {
        e.stopPropagation();

        const message_id = rows.get_message_id(this);
        exports.toggle_emoji_popover(this, message_id);
    });

    $("#main_div").on("mouseenter", ".reaction_button", function (e) {
        e.stopPropagation();

        const elem = $(e.currentTarget);
        const title = i18n.t("Add emoji reaction");
        elem.tooltip({
            title: title + " (:)",
            trigger: 'hover',
            placement: 'bottom',
            animation: false,
        });
        elem.tooltip('show');
        $(".tooltip-arrow").remove();
    });

    $('#main_div').on('mouseleave', '.reaction_button', function (e) {
        e.stopPropagation();
        $(e.currentTarget).tooltip('hide');
    });

    $("body").on("click", ".actions_popover .reaction_button", function (e) {
        const message_id = $(e.currentTarget).data('message-id');
        e.preventDefault();
        e.stopPropagation();
        // HACK: Because we need the popover to be based off an
        // element that definitely exists in the page even if the
        // message wasn't sent by us and thus the .reaction_hover
        // element is not present, we use the message's
        // .fa-chevron-down element as the base for the popover.
        const elem = $(".selected_message .actions_hover")[0];
        exports.toggle_emoji_popover(elem, message_id);
    });

    $("body").on("click", ".emoji-popover-tab-item", function (e) {
        e.stopPropagation();
        e.preventDefault();
        const offset = section_head_offsets.find(function (o) {
            return o.section === $(this).attr("data-tab-name");
        }.bind(this));

        if (offset) {
            ui.get_scroll_element($(".emoji-popover-emoji-map")).scrollTop(offset.position_y);
        }
    });

    $("body").on("click", ".emoji-popover-filter", function () {
        reset_emoji_showcase();
    });

    $("body").on("mouseenter", ".emoji-popover-emoji", function () {
        const emoji_id = $(this).data("emoji-id");
        const emoji_coordinates = get_emoji_coordinates(emoji_id);

        may_be_change_focused_emoji(emoji_coordinates.section, emoji_coordinates.index, true);
    });
};

exports.is_composition = function (emoji) {
    return $(emoji).hasClass('composition');
};

exports.initialize = function () {
    exports.generate_emoji_picker_data(emoji.active_realm_emojis);
};

window.emoji_picker = exports;
