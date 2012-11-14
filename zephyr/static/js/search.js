var search = (function () {

var exports = {};

var cached_term = "";
var cached_matches = [];
var cached_index;
var cached_table = $('table.focused_table');

function narrow_or_search_for_term(item) {
    console.log("Narrowing or searching for", item);
    return item;
}

exports.initialize = function () {
    $( "#search_query" ).typeahead({
        source: function (query, process) {
            return stream_list;
        },
        items: 3,
        highlighter: composebox_typeahead.escaping_typeahead_highlighter,
        updater: narrow_or_search_for_term
    });

    $("#searchbox_form").keydown(function (e) {
        var code = e.which;
        if (code === 13 && $("#search_query").data().typeahead.shown) {
            // We pressed Enter and the typeahead is open;
            // don't submit the form so that the typeahead
            // can instead handle our Enter keypress.
            e.preventDefault();
            return false;
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
