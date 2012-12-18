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
        return {action: 'Find', search: obj.query};

    case 'stream':
        return {action: 'Narrow to stream', search: obj.query};

    case 'private_message':
        return {action: 'Narrow to person',
                search: typeahead_helper.render_pm_object(obj.query)};

    case 'operators':
        // HACK: This label needs to be distinct from the above, because of the
        // way we identify action objects by their labels.  Using two spaces
        // after 'Narrow to' ensures this, and is invisible with standard HTML
        // whitespace handling.
        return {action: 'Narrow to  ', search: narrow.describe(obj.operators)};
    }
    return {action: 'Error', search: 'Error'};
}

function render_object(obj) {
    var parts = render_object_in_parts(obj);
    return parts.action + " " + parts.search;
}

exports.update_typeahead = function () {
    var streams = $.map(stream_list, function(elt,idx) {
        return {action: 'stream', query: elt};
    });
    var people = $.map(people_list, function(elt,idx) {
        return {action: 'private_message', query: elt};
    });
    var options = streams.concat(people);
    // The first two slots are reserved for our query.
    options.unshift({action: 'operators', query: '', operators: []});
    options.unshift({action: 'search', query: ''});

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
    switch (obj.action) {
    case 'search':
        $("#search_up").focus();
        exports.search_button_handler(true);
        return obj.query;

    case 'stream':
        narrow.activate([['stream', obj.query]]);
        // It's sort of annoying that this is not in a position to
        // blur the search box, because it means that Esc won't
        // unnarrow, it'll leave the searchbox.

        // Narrowing will have already put some operators in the search box,
        // so leave the current text in.
        return search_query_box.val();

    case 'private_message':
        narrow.activate([['pm-with', obj.query.email]], {show_floating_recipient: false});
        return search_query_box.val();

    case 'operators':
        narrow.activate(obj.operators);
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
    $.each(['search', 'operators', 'stream', 'private_message'], function (idx, action) {
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

exports.initialize = function () {
    $( "#search_query" ).typeahead({
        source: function (query, process) {
            // Delete our old search queries (one for find-in-page, one for operators)
            var i;
            for (i=0; i<2; i++) {
                delete mapped[labels.shift()];
            }

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
            labels.unshift(label);

            return labels;
        },
        items: 4,
        highlighter: function (item) {
            var query = this.query;
            var parts = render_object_in_parts(mapped[item]);
            // We provide action, not the user, so this should
            // be fine from a not-needing-escaping perspective.
            return parts.action + " " +
                typeahead_helper.highlight_with_escaping(query, parts.search);
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
        var code = e.which;
        var search_query_box = $("#search_query");
        if (code === 13 && search_query_box.is(":focus")) {
            // Don't submit the form so that the typeahead can instead
            // handle our Enter keypress. Any searching that needs
            // to be done will be handled in the keyup.
            e.preventDefault();
            return false;
        }
    });
    $("#searchbox_form").keyup(function (e) {
        var code = e.which;
        var search_query_box = $("#search_query");
        if (code === 13 && search_query_box.is(":focus")) {
            // We just pressed enter and the box had focus, so one of
            // two things is true:
            // 1) There's a value in the search box and we should
            // search for it
            // 2) There's no value in the searchbox, so we just
            // narrowed, so we should blur the box.
            //
            // Note that if the typeahead completion box was up, it
            // has already handled the keypress and defocused the
            // box.  So we only get here when enter was pressed while
            // the completion box was not displayed.
            if (search_query_box.val()) {
                $("#search_up").focus();
                exports.search_button_handler(true);
            } else {
                exports.clear_search();
                search_query_box.blur();
            }
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
    row.highlight(search_term);

    row = row.prev('.recipient_row');
    if ((row.length !== 0) && (match_on_visible_text(row, search_term))) {
        row.highlight(search_term);
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
    if (!$('.search_button').is(':visible')) {
        // Shrink the searchbox to make room for the buttons.
        var search_query = $('#search_query');
        var new_width = search_query.width() -
            $('.search_button').outerWidth(true)*3;
        search_query.width(new_width);
        $("#search_arrows").addClass("input-append");
        $('.search_button').show();
        disable_search_arrows_if(false, ["up", "down"]);
    }
};

exports.initiate_search = function () {
    $('#search_query').val('').focus();
};

exports.clear_search = function () {
    narrow.deactivate();
    $('table tr').removeHighlight();
    // Clear & reset searchbox to its normal size
    $('#search_query').val('').width('');
    $("#search_arrows").removeClass("input-append");
    $("#search_up, #search_down").removeAttr("disabled");
    $('.search_button').blur().hide();
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
