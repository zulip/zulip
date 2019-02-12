var floating_recipient_bar = (function () {

var exports = {};


var is_floating_recipient_bar_showing = false;

function top_offset(elem) {
    return elem.offset().top - $('#tab_bar').safeOuterHeight();
}

exports.first_visible_message = function (bar) {
    // The first truly visible message would be computed using the
    // bottom of the floating recipient bar; but we want the date from
    // the first visible message were the floating recipient bar not
    // displayed, which will always be the first messages whose bottom
    // overlaps the floating recipient bar's space (since you ).

    var messages = bar.children('.message_row');
    var frb_bottom = exports.frb_bottom();
    var frb_top = frb_bottom - 25;
    var result;

    for (var i = 0; i < messages.length; i += 1) {
        // The details of this comparison function are sensitive, since we're
        // balancing between three possible bugs:
        //
        // * If we compare against the bottom of the floating
        //   recipient bar, we end up with a bug where if the floating
        //   recipient bar is just above a normal recipient bar while
        //   overlapping a series of 1-line messages, there might be 2
        //   messages occluded by the recipient bar, and we want the
        //   second one, not the first.
        //
        // * If we compare the message bottom against the top of the
        //   floating recipient bar, and the floating recipient bar is
        //   over a "Yesterday/Today" message date row, we might
        //   confusingly have the floating recipient bar display
        //   e.g. "Yesterday" even though all messages in view were
        //   actually sent "Today".
        //
        // * If the the floating recipient bar is over a
        //   between-message groups date separator or similar widget,
        //   there might be no message overlap with the floating
        //   recipient bar.
        //
        // Careful testing of these two corner cases with
        // message_viewport.scrollTop() to set precise scrolling
        // positions determines the value for date_bar_height_offset.

        var message = $(messages[i]);
        var message_bottom = top_offset(message) + message.safeOuterHeight();
        var date_bar_height_offset = 10;

        if (message_bottom > frb_top) {
            result = message;
        }

        // Important: This will break if we ever have things that are
        // not message rows inside a recipient_row block.
        message = message.next('.message_row');
        if (message.length > 0 && result) {
            // Before returning a result, we check whether the next
            // message's top is actually below the bottom of the
            // floating recipient bar; this is different from the
            // bottom of our current message because there may be a
            // between-messages date separator row in between.
            if (top_offset(message) < frb_bottom - date_bar_height_offset) {
                result = message;
            }
        }
        if (result) {
            return result;
        }
    }

    // If none of the messages are visible, just take the last message.
    return $(messages[messages.length - 1]);
};

exports.get_date = function (elem) {
    var message_row = exports.first_visible_message(elem);

    if (!message_row || !message_row.length) {
        return;
    }

    var msg_id = rows.id(message_row);

    if (msg_id === undefined) {
        return;
    }

    var message = message_store.get(msg_id);

    if (!message) {
        return;
    }

    var time = new XDate(message.timestamp * 1000);
    var today = new XDate();
    var rendered_date = timerender.render_date(time, undefined, today)[0].outerHTML;

    return rendered_date;
};

exports.frb_bottom = function () {
    var bar = $("#floating_recipient_bar");
    var bar_top = top_offset(bar);
    var bar_bottom = bar_top + bar.safeOuterHeight();

    return bar_bottom;
};

exports.relevant_recipient_bars = function () {
    var elems = [];

    // This line of code does a reverse traversal
    // from the selected message, which should be
    // in the visible part of the feed, but is sometimes
    // not exactly where we want.  The value we get
    // may be be too far up in the feed, but we can
    // deal with that later.
    var first_elem = exports.candidate_recipient_bar();

    if (!first_elem) {
        first_elem = $('.focused_table').find('.recipient_row').first();
    }

    if (first_elem.length === 0) {
        return [];
    }

    elems.push(first_elem);

    var max_offset = top_offset($('#compose'));
    var header_height = first_elem.find('.message_header').safeOuterHeight();

    // It's okay to overestimate header_height a bit, as we don't
    // really need an FRB for a section that barely shows.
    header_height += 10;

    function next(elem) {
        elem = elem.next();
        while (elem.length !== 0 && !elem.hasClass("recipient_row")) {
            elem = elem.next();
        }
        return elem;
    }

    // Now start the forward traversal of recipient bars.
    // We'll stop when we go below the fold.
    var elem = next(first_elem);

    while (elem.length) {

        if (top_offset(elem) < header_height) {
            // If we are close to the top, then the prior
            // elements we found are no longer relevant,
            // because either the selected item we started
            // with in our reverse traversal was too high,
            // or there's simply not enough room to draw
            // a recipient bar without it being ugly.
            elems = [];
        }

        if (top_offset(elem) > max_offset) {
            // Out of sight, out of mind!
            // (The element is below the fold, so we stop the
            // traversal.)
            break;
        }

        elems.push(elem);
        elem = next(elem);
    }

    if (elems.length === 0) {
        blueslip.warn('Unexpected situation--maybe viewport height is very short.');
        return [];
    }

    var items = _.map(elems, function (elem, i) {
        var date_html;
        var need_frb;

        if (i === 0) {
            date_html = exports.get_date(elem);
            need_frb = top_offset(elem) < 0;
        } else {
            date_html = elem.find('.recipient_row_date').html();
            need_frb = false;
        }

        var date_text = $(date_html).text();

        // Add title here to facilitate troubleshooting.
        var title = elem.find('.message_label_clickable').last().attr('title');

        var item = {
            elem: elem,
            title: title,
            date_html: date_html,
            date_text: date_text,
            need_frb: need_frb,
        };

        return item;
    });

    items[0].show_date = true;

    for (var i = 1; i < items.length; i += 1) {
        items[i].show_date = items[i].date_text !== items[i - 1].date_text;
    }

    _.each(items, function (item) {
        if (!item.need_frb) {
            delete item.date_html;
        }
    });

    return items;
};

exports.candidate_recipient_bar = function () {
    // Find a recipient bar that is close to being onscreen
    // but above the "top".  This function is guaranteed to
    // return **some** recipient bar that is above the fold,
    // if there is one, but it may not be the optimal one if
    // our pointer is messed up.  Starting with the pointer
    // is just an optimization here, and our caller will do
    // a forward traversal and clean up as necessary.
    // In most cases we find the bottom-most of recipient
    // bars that is still above the fold.

    // Start with the pointer's current location.
    var selected_row = current_msg_list.selected_row();

    if (selected_row === undefined || selected_row.length === 0) {
        return;
    }

    var candidate = rows.get_message_recipient_row(selected_row);
    if (candidate === undefined) {
        return;
    }

    while (candidate.length) {

        if (candidate.hasClass("recipient_row") && top_offset(candidate) < 0) {
            return candidate;
        }
        // We cannot use .prev(".recipient_row") here, because that
        // returns nothing if the previous element is not a recipient
        // row, rather than finding the first recipient_row.
        candidate = candidate.prev();
    }
};

function show_floating_recipient_bar() {
    if (!is_floating_recipient_bar_showing) {
        $("#floating_recipient_bar").css('visibility', 'visible');
        is_floating_recipient_bar_showing = true;
    }
}

var old_source;
function replace_floating_recipient_bar(source_info) {

    var source_recipient_bar = source_info.elem;

    var new_label;
    var other_label;
    var header;

    if (source_recipient_bar !== old_source) {
        if (source_recipient_bar.children(".message_header_stream").length !== 0) {
            new_label = $("#current_label_stream");
            other_label = $("#current_label_private_message");
            header = source_recipient_bar.children(".message_header_stream");
        } else {
            new_label = $("#current_label_private_message");
            other_label = $("#current_label_stream");
            header = source_recipient_bar.children(".message_header_private_message");
        }
        new_label.find(".message_header").replaceWith(header.clone());
        other_label.css('display', 'none');
        new_label.css('display', 'block');
        new_label.attr("zid", rows.id(rows.first_message_in_group(source_recipient_bar)));

        new_label.toggleClass('message-fade', source_recipient_bar.hasClass('message-fade'));
        old_source = source_recipient_bar;
    }

    var rendered_date = source_info.date_html || '';

    $('#floating_recipient_bar').find('.recipient_row_date').html(rendered_date);

    show_floating_recipient_bar();
}

exports.hide = function () {
    if (is_floating_recipient_bar_showing) {
        $("#floating_recipient_bar").css('visibility', 'hidden');
        is_floating_recipient_bar_showing = false;
    }
};

exports.de_clutter_dates = function (items) {
    _.each(items, function (item) {
        item.elem.find('.recipient_row_date').toggle(item.show_date);
    });
};

exports.update = function () {
    var items = exports.relevant_recipient_bars();

    if (!items || items.length === 0) {
        exports.hide();
        return;
    }

    exports.de_clutter_dates(items);

    if (!items[0].need_frb) {
        exports.hide();
        return;
    }

    replace_floating_recipient_bar(items[0]);
};


return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = floating_recipient_bar;
}
window.floating_recipient_bar = floating_recipient_bar;
