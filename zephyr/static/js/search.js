var cached_term = "";
var cached_matches = [];
var cached_index;
var cached_table = $('table.focused_table');

function get_zid_as_int(object) {
    return parseInt(object.attr("zid"), 10);
}

function match_on_visible_text(row, search_term) {
    // You can't select on :visible, since that includes hidden elements that
    // take up space.
    return row.find(".message_content, .sender_name, .message_header, .message_time")
              .text().toLowerCase().indexOf(search_term) !== -1;
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
        var selected_zid = get_zid_as_int(highlighted_message);

        focused_table.find('.message_row, .recipient_row').each(function (index, row) {
            row = $(row);
            if (previous_header_matched || (match_on_visible_text(row, term))) {
                previous_header_matched = false;

                if (row.hasClass("recipient_row")) {
                    previous_header_matched = true;
                } else {
                    cached_matches.push(row);
                    var zid = get_zid_as_int(row);
                    if ((reverse && (zid <= selected_zid)) ||
                        (!reverse && (zid >= selected_zid) && !cached_index)) {
                        // Keep track of the closest match going up or down.
                        cached_index = cached_matches.length - 1;
                    }
                }
            }
        });

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

function search_button_handler(reverse) {
    var query = $('#search').val().toLowerCase();
    var res = search(query, selected_message, reverse);
    if (!res) {
        return;
    }

    select_message_by_id(res.attr("zid"));
    highlight_match(res, query);
    scroll_to_selected();
}

function clear_search_cache() {
    cached_term = "";
}

function focus_search() {
    $("#search").width("504px");
    $("#search_arrows").addClass("input-append");
    $('.search_button').show();
}

function initiate_search() {
    $('#search').val('').focus();
}

function clear_search() {
    $('table tr').removeHighlight();
    // Reset the width to that in the stylesheet. If you change it there, change
    // it here.
    $('#search').val('').width("610px");
    $("#search_arrows").removeClass("input-append");
    $('.search_button').hide();
    clear_search_cache();
}

function something_is_highlighted() {
    return $(".highlight").length > 0;
}

function update_highlight_on_narrow() {
    highlight_match(selected_message, cached_term);
    clear_search_cache();
}
