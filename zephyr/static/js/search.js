var search = (function () {

var exports = {};

var cached_term = "";
var cached_matches = [];
var cached_index;
var cached_table = $('table.focused_table');

// Data storage for the typeahead -- to go from object to string representation and vice versa.
var labels = [];
var mapped = {};

function render_object_in_parts(obj) {
    // N.B. action is *not* escaped by the caller
    switch (obj.action) {
    case 'search':
        return {prefix: 'Find', query: obj.query, suffix: 'in page'};

    case 'stream':
        return {prefix: 'Narrow to stream', query: obj.query, suffix: ''};

    case 'private_message':
        return {prefix: 'Narrow to person',
                query: typeahead_helper.render_pm_object(obj.query),
                suffix: ''};

    case 'operators':
        // HACK: This label needs to be distinct from the above, because of the
        // way we identify action objects by their labels.  Using two spaces
        // after 'Narrow to' ensures this, and is invisible with standard HTML
        // whitespace handling.
        return {prefix: 'Narrow to  ',
                query: narrow.describe(obj.operators),
                suffix: ''};
    }
    return {prefix: 'Error', query: 'Error', suffix: 'Error'};
}

function render_object(obj) {
    var parts = render_object_in_parts(obj);
    return parts.prefix + " " + parts.query + " " + parts.suffix;
}

exports.update_typeahead = function () {
    var streams = $.map(subs.subscribed_streams(), function(elt,idx) {
        return {action: 'stream', query: elt};
    });
    var people = $.map(people_list, function(elt,idx) {
        return {action: 'private_message', query: elt};
    });
    var options = streams.concat(people);
    // The first slot is reserved for "narrow to messages containing x",
    // and the last one for "Find in page"
    // (this is updated in the source function for our typeahead as well)
    options.unshift({action: 'operators', query: '', operators: []});
    options.push({action: 'search', query: ''});

    mapped = {};
    labels = [];
    $.each(options, function (i, obj) {
        var label = render_object(obj);
        mapped[label] = obj;
        labels.push(label);
    });
};

function narrow_or_search_for_term(item) {
    var search_query_box = $("#search_query");
    var obj = mapped[item];
    ui.change_tab_to('#home');
    switch (obj.action) {
    case 'search':
        $("#search_up").focus();
        exports.search_button_handler(true);
        return obj.query;

    case 'stream':
        narrow.by('stream', obj.query);
        // It's sort of annoying that this is not in a position to
        // blur the search box, because it means that Esc won't
        // unnarrow, it'll leave the searchbox.

        // Narrowing will have already put some operators in the search box,
        // so leave the current text in.
        search_query_box.blur();
        return search_query_box.val();

    case 'private_message':
        narrow.by('pm-with', obj.query.email);
        search_query_box.blur();
        return search_query_box.val();

    case 'operators':
        narrow.activate(obj.operators);
        search_query_box.blur();
        return search_query_box.val();
    }
    return item;
}

function get_query(obj) {
    return obj.query;
}

function get_person(obj) {
    return typeahead_helper.render_pm_object(obj.query);
}

function searchbox_sorter(items) {
    var objects_by_action = {};
    var result = [];

    $.each(items, function (idx, elt) {
        var obj = mapped[elt];
        if (objects_by_action[obj.action] === undefined)
            objects_by_action[obj.action] = [];
        objects_by_action[obj.action].push(obj);
    });

    var query = this.query;
    $.each(['operators', 'stream', 'private_message', 'search'], function (idx, action) {
        var objs = objects_by_action[action];
        if (!objs)
            return;
        // Get the first object in sorted order.
        var obj = typeahead_helper.sorter(query, objs,
                (action === 'private_message') ? get_person : get_query)
            .shift();
        if (obj)
            result.push(render_object(obj));
    });

    return result;
}

function update_buttons_with_focus(focused) {
    var search_query = $('#search_query');

    // Show buttons iff the search input is focused, or has non-empty contents,
    // or we are narrowed.
    if (focused
        || search_query.val()
        || narrow.active()) {

        if ($('.search_button').is(':visible')) {
            // Already visible, and the width manipulation below
            // will break if we do it again.
            return;
        }
        // Shrink the searchbox to make room for the buttons.
        var new_width = search_query.width() -
            $('.search_button').outerWidth(true)*3;
        search_query.width(new_width-1);
        $("#search_arrows").addClass("input-append");
        $('.search_button').show();
    } else {
        // Hide buttons.
        $('#search_query').width('');
        $("#search_arrows").removeClass("input-append");
        $("#search_up, #search_down").removeAttr("disabled");
        $('.search_button').blur().hide();
    }
}

exports.update_button_visibility = function () {
    update_buttons_with_focus($('#search_query').is(':focus'));
};

exports.initialize = function () {
    $( "#search_query" ).typeahead({
        source: function (query, process) {
            // Delete our old search queries (one for find-in-page, one for operators)
            delete mapped[labels.shift()]; // Operators
            delete mapped[labels.pop()]; // Find-in-page

            // Add an entry for narrow by operators.
            var operators = narrow.parse(query);
            var obj = {action: 'operators', query: query, operators: operators};
            var label = render_object(obj);
            mapped[label] = obj;
            labels.unshift(label);

            // Add an entry for find-in-page.
            obj = {action: 'search', query: query};
            if (operators.length > 0 && operators[0][0] !== 'search') {
                // We have operators other than a search term.
                // Disable find-in-page.
                obj.disabled = true;
            }
            label = render_object(obj);
            mapped[label] = obj;
            labels.push(label);

            return labels;
        },
        items: 4,
        highlighter: function (item) {
            var query = this.query;
            var parts = render_object_in_parts(mapped[item]);
            // We provide action, not the user, so this should
            // be fine from a not-needing-escaping perspective.
            return parts.prefix + " " +
                typeahead_helper.highlight_with_escaping(query, parts.query)
                + " " + parts.suffix;
        },
        matcher: function (item) {
            var obj = mapped[item];
            if (obj.disabled)
                return false;
            var actual_search_term = obj.query;
            if (obj.action === 'private_message') {
                actual_search_term = obj.query.full_name + ' <' + obj.query.email + '>';
            }
            // Case-insensitive (from Bootstrap's default matcher).
            return (actual_search_term.toLowerCase().indexOf(this.query.toLowerCase()) !== -1);
        },
        updater: narrow_or_search_for_term,
        sorter: searchbox_sorter
    });

    $("#searchbox_form").keydown(function (e) {
        exports.update_button_visibility();
        var code = e.which;
        var search_query_box = $("#search_query");
        if (code === 13 && search_query_box.is(":focus")) {
            // Don't submit the form so that the typeahead can instead
            // handle our Enter keypress. Any searching that needs
            // to be done will be handled in the keyup.
            e.preventDefault();
            return false;
        }
    }).keyup(function (e) {
        var code = e.which;
        var search_query_box = $("#search_query");
        if (code === 13 && search_query_box.is(":focus")) {
            // We just pressed enter and the box had focus, which
            // means we didn't use the typeahead at all.  In that
            // case, we should act as though we're searching by
            // operators.  (The reason the other actions don't call
            // this codepath is that they first all blur the box to
            // indicate that they've done what they need to do)
            if (search_query_box.val()) {
                narrow.activate(narrow.parse(search_query_box.val()));
            }
            search_query_box.blur();
            update_buttons_with_focus(false);
        }
    });
};

function match_on_visible_text(row, search_term) {
    // You can't select on :visible, since that includes hidden elements that
    // take up space.
    return row.find(".message_content, .sender_name, .message_header, .message_time")
              .text().toLowerCase().indexOf(search_term) !== -1;
}

function disable_search_arrows_if(condition, affected_arrows) {
    var i, button;

    for (i = 0; i < affected_arrows.length; i++) {
        button = $("#search_" + affected_arrows[i]);
        if (condition) {
            button.attr("disabled", "disabled");
        } else {
            button.removeAttr("disabled");
        }
    }
}

function search(term, highlighted_message, reverse) {
    // term: case-insensitive text to search for
    // highlighted_message: the current location of the pointer. Ignored
    //     on cached queries
    // reverse: boolean as to whether the search is forward or backwards
    //
    // returns a message object containing the search term.
    var previous_header_matched = false;

    var focused_table = $('table.focused_table');
    if ((term !== cached_term) || (cached_table[0] !== focused_table[0])) {
        cached_term = term;
        cached_matches = [];
        cached_index = null;
        cached_table = focused_table;
        var selected_zid = rows.id(highlighted_message);

        focused_table.find('.message_row, .recipient_row').each(function (index, row) {
            row = $(row);
            if (previous_header_matched || (match_on_visible_text(row, term))) {
                previous_header_matched = false;

                if (row.hasClass("recipient_row")) {
                    previous_header_matched = true;
                } else {
                    cached_matches.push(row);
                    var zid = rows.id(row);
                    if ((reverse && (zid <= selected_zid)) ||
                        (!reverse && (zid >= selected_zid) && !cached_index)) {
                        // Keep track of the closest match going up or down.
                        cached_index = cached_matches.length - 1;
                    }
                }
            }
        });

        disable_search_arrows_if(cached_matches.length === 0, ["up", "down"]);

        return cached_matches[cached_index];
    }

    if (reverse) {
        if (cached_index > 0) {
            cached_index--;
        }
    } else {
        if (cached_index < cached_matches.length - 1) {
            cached_index++;
        }
    }

    disable_search_arrows_if(cached_matches.length === 0, ["up", "down"]);
    disable_search_arrows_if(cached_index === 0, ["up"]);
    disable_search_arrows_if(cached_index === cached_matches.length - 1, ["down"]);

    return cached_matches[cached_index];
}

function highlight_match(row, search_term) {
    $('table tr').removeHighlight();
    row.find('.message_content').highlight(search_term);

    row = row.prev('.recipient_row');
    if ((row.length !== 0) && (match_on_visible_text(row, search_term))) {
        row.find('.message_label_clickable').highlight(search_term);
    }
}

exports.search_button_handler = function (reverse) {
    var query = $('#search_query').val().toLowerCase();
    var res = search(query, selected_message, reverse);
    if (!res) {
        return;
    }

    select_message(res);
    highlight_match(res, query);
    scroll_to_selected();
};

function clear_search_cache() {
    cached_term = "";
}

exports.focus_search = function () {
    // The search bar is not focused yet, but will be.
    update_buttons_with_focus(true);
    disable_search_arrows_if(false, ["up", "down"]);
};

exports.initiate_search = function () {
    $('#search_query').select();
};

exports.clear_search = function () {
    narrow.deactivate();
    $('table tr').removeHighlight();
    // Clear & reset searchbox to its normal size
    $('#search_query').val('').blur();
    exports.update_button_visibility();
    clear_search_cache();
};

exports.something_is_highlighted = function () {
    return $(".highlight").length > 0;
};

exports.update_highlight_on_narrow = function () {
    highlight_match(selected_message, cached_term);
    clear_search_cache();
};

exports.keyboard_currently_finding = function () {
    // This is somewhat subtle because it doesn't actually mean
    // "is a find in progress" -- it means "is the keyboard
    // currently driving a find"
    // (If you have a Find going and you just click the button,
    // the focus goes away and this starts being False,
    // even though a find is still active.)
    return $('.search_button').is(':focus');
};

return exports;

}());
