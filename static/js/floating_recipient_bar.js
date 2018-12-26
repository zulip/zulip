var floating_recipient_bar = (function () {

var exports = {};


var is_floating_recipient_bar_showing = false;

exports.frb_bottom = function () {
    var bar = $("#floating_recipient_bar");
    var bar_top = bar.offset().top;
    var bar_bottom = bar_top + bar.safeOuterHeight();

    return bar_bottom;
};

exports.obscured_recipient_bar = function () {
    // Find the recipient bar that is closed to being onscreen
    // but above the "top".

    // Start with the pointer's current location.
    var selected_row = current_msg_list.selected_row();

    if (selected_row === undefined || selected_row.length === 0) {
        return;
    }

    var candidate = rows.get_message_recipient_row(selected_row);
    if (candidate === undefined) {
        return;
    }

    var floating_recipient_bar_bottom = exports.frb_bottom();

    while (candidate.length) {
        if (candidate.is(".recipient_row")) {
            if (candidate.offset().top < floating_recipient_bar_bottom) {
                return candidate;
            }
        }
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
function replace_floating_recipient_bar(source_recipient_bar) {
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
    show_floating_recipient_bar();
}

exports.hide = function () {
    if (is_floating_recipient_bar_showing) {
        $("#floating_recipient_bar").css('visibility', 'hidden');
        is_floating_recipient_bar_showing = false;
    }
};

exports.update = function () {
    // .temp-show-date might be forcing the display of a recipient_row_date if
    // the floating_recipient_bar is just beginning to overlap the
    // top-most recipient_bar. remove all instances of .temp-show-date and
    // re-apply it if we continue to detect overlap
    $('.temp-show-date').removeClass('temp-show-date');

    var floating_recipient_bar_bottom = exports.frb_bottom();

    var source_recipient_bar = exports.obscured_recipient_bar();

    if (!source_recipient_bar) {
        exports.hide();
        return;
    }

    // We now know what the floating stream/topic bar should say.
    // Do we show it?

    // Hide if the bottom of our floating stream/topic label is not
    // lower than the bottom of source_recipient_bar (since that means we're
    // covering up a label that already exists).
    var header_height = $(source_recipient_bar).find('.message_header').safeOuterHeight();
    if (floating_recipient_bar_bottom <=
        source_recipient_bar.offset().top + header_height) {
        // hide floating_recipient_bar and use .temp-show-date to force display
        // of the recipient_row_date belonging to the current recipient_bar
        $('.recipient_row_date', source_recipient_bar).addClass('temp-show-date');
        exports.hide();
        return;
    }

    replace_floating_recipient_bar(source_recipient_bar);
};


return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = floating_recipient_bar;
}
window.floating_recipient_bar = floating_recipient_bar;
