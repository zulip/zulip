var search = (function () {

var exports = {};

var cached_term = "";
var cached_matches = [];
var cached_index;
var cached_table = $('table.focused_table');

// Data storage for the typeahead -- to go from object to string representation and vice versa.
var labels = [];
var mapped = {};

function render_object(obj) {
    if (obj.action === 'search') {
        return "Find " + obj.query;
    } else if (obj.action === 'stream') {
        return "Narrow to stream " + obj.query;
    } else if (obj.action === 'private_message') {
        return "Narrow to person " +
            typeahead_helper.render_pm_object(obj.query);
    } else if (obj.action === 'search_narrow') {
        return "Narrow to messages containing " + obj.query;
    }
    return "Error";
}

exports.update_typeahead = function() {
    var streams = $.map(stream_list, function(elt,idx) {
        return {action: 'stream', query: elt};
    });
    var people = $.map(people_list, function(elt,idx) {
        return {action: 'private_message', query: elt};
    });
    var options = streams.concat(people);
    // The first two slots are reserved for our query.
    options.unshift({action: 'search_narrow', query: ''});
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
    var obj = mapped[item];
    if (obj.action === "search") {
        return obj.query;
    } else if (obj.action === "stream") {
        narrow.by_stream_name(obj.query);
        // It's sort of annoying that this is not in a position to
        // blur the search box, because it means that Esc won't
        // unnarrow, it'll leave the searchbox.
        return ""; // Keep the search box empty
    } else if (obj.action === "private_message") {
        narrow.by_private_message_partner(obj.query.full_name, obj.query.email);
        return "";
    } else if (obj.action === "search_narrow") {
        narrow.by_search_term(obj.query);
        return "";
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
    var searches = [];
    var search_narrows = [];
    var streams = [];
    var people = [];
    var objects = [];

    $.each(items, function (idx, elt) {
        var obj = mapped[elt];
        if (obj.action === 'stream') {
            streams.push(obj);
        } else if (obj.action === 'private_message') {
            people.push(obj);
        } else if (obj.action === 'search') {
            searches.push(obj);
        } else if (obj.action === 'search_narrow') {
            search_narrows.push(obj);
        }
    });

    searches = typeahead_helper.sorter(this.query, searches, get_query);
    search_narrows = typeahead_helper.sorter(this.query, search_narrows, get_query);
    streams = typeahead_helper.sorter(this.query, streams, get_query);
    people = typeahead_helper.sorter(this.query, people, get_person);

    $.each([searches, search_narrows, streams, people], function (idx, elt) {
        var obj = elt.shift();
        if (obj) objects.push(obj);
    });

    return $.map(objects, function (elt, idx) {
        return render_object(elt);
    });
}

exports.initialize = function () {
    $( "#search_query" ).typeahead({
        source: function (query, process) {
            // Delete our old search queries (one for search-in-page, one for search-history)
            var old_search_label = labels.shift();
            delete mapped[old_search_label];
            var old_search_narrow_label = labels.shift();
            delete mapped[old_search_narrow_label];
            // Add our new ones
            var obj = {action: 'search_narrow', query: query};
            var label = render_object(obj);
            mapped[label] = obj;
            labels.unshift(label);
            obj = {action: 'search', query: query};
            label = render_object(obj);
            mapped[label] = obj;
            labels.unshift(label);
            return labels;
        },
        items: 4,
        highlighter: function (item) {
            var query = this.query;
            var string_item = render_object(mapped[item]);
            return typeahead_helper.highlight_with_escaping(query, string_item);
        },
        matcher: function (item) {
            var obj = mapped[item];
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

return exports;

}());
