var ui = (function () {

var exports = {};

var actively_scrolling = false;
var narrow_window = false;

exports.actively_scrolling = function () {
    return actively_scrolling;
};

// What, if anything, obscures the home tab?
exports.home_tab_obscured = function () {
    if ($('.modal:visible').length > 0) {
        return 'modal';
    }
    if (! $('#home').hasClass('active')) {
        return 'other_tab';
    }
    return false;
};

// We want to remember how far we were scrolled on each 'tab'.
// To do so, we need to save away the old position of the
// scrollbar when we switch to a new tab (and restore it
// when we switch back.)
var scroll_positions = {};

exports.change_tab_to = function (tabname) {
    $('#gear-menu a[href="' + tabname + '"]').tab('show');
};

exports.focus_on = function (field_id) {
    // Call after autocompleting on a field, to advance the focus to
    // the next input field.

    // Bootstrap's typeahead does not expose a callback for when an
    // autocomplete selection has been made, so we have to do this
    // manually.
    $("#" + field_id).focus();
};

function amount_to_paginate() {
    // Some day we might have separate versions of this function
    // for Page Up vs. Page Down, but for now it's the same
    // strategy in either direction.
    var info = viewport.message_viewport_info();
    var page_size = info.visible_height;

    // We don't want to page up a full page, because Zulip users
    // are especially worried about missing messages, so we want
    // a little bit of the old page to stay on the screen.  The
    // value chosen here is roughly 2 or 3 lines of text, but there
    // is nothing sacred about it, and somebody more anal than me
    // might wish to tie this to the size of some particular DOM
    // element.
    var overlap_amount = 55;

    var delta = page_size - overlap_amount;

    // If the user has shrunk their browser a whole lot, pagination
    // is not going to be very pleasant, but we can at least
    // ensure they go in the right direction.
    if (delta < 1) {
        delta = 1;
    }

    return delta;
}

exports.page_up_the_right_amount = function () {
    // This function's job is to scroll up the right amount,
    // after the user hits Page Up.  We do this ourselves
    // because we can't rely on the browser to account for certain
    // page elements, like the compose box, that sit in fixed
    // positions above the message pane.  For other scrolling
    // related adjustements, try to make those happen in the
    // scroll handlers, not here.
    var delta = amount_to_paginate();
    viewport.scrollTop(viewport.scrollTop() - delta);
};

exports.page_down_the_right_amount = function () {
    // see also: page_up_the_right_amount
    var delta = amount_to_paginate();
    viewport.scrollTop(viewport.scrollTop() + delta);
};

function find_boundary_tr(initial_tr, iterate_row) {
    var j, skip_same_td_check = false;
    var tr = initial_tr;

    // If the selection boundary is somewhere that does not have a
    // parent tr, we should let the browser handle the copy-paste
    // entirely on its own
    if (tr.length === 0) {
        return undefined;
    }

    // If the selection bounary is on a table row that does not have an
    // associated message id (because the user clicked between messages),
    // then scan downwards until we hit a table row with a message id.
    // To ensure we can't enter an infinite loop, bail out (and let the
    // browser handle the copy-paste on its own) if we don't hit what we
    // are looking for within 10 rows.
    for (j = 0; (!tr.is('.message_row')) && j < 10; j++) {
        tr = iterate_row(tr);
    }
    if (j === 10) {
        return undefined;
    } else if (j !== 0) {
        // If we updated tr, then we are not dealing with a selection
        // that is entirely within one td, and we can skip the same td
        // check (In fact, we need to because it won't work correctly
        // in this case)
        skip_same_td_check = true;
    }
    return [rows.id(tr), skip_same_td_check];
}

exports.replace_emoji_with_text = function (element) {
    element.find(".emoji").replaceWith(function () {
        return $(this).attr("alt");
    });
};

function copy_handler(e) {
    var selection = window.getSelection();
    var i, range, ranges = [], startc, endc, initial_end_tr, start_id, end_id, row, message;
    var start_data, end_data;
    var skip_same_td_check = false;
    var div = $('<div>'), content;
    for (i = 0; i < selection.rangeCount; i++) {
        range = selection.getRangeAt(i);
        ranges.push(range);

        startc = $(range.startContainer);
        start_data = find_boundary_tr($(startc.parents('tr')[0]), function (row) {
            return row.next();
        });
        if (start_data === undefined) {
            return;
        }
        start_id = start_data[0];

        endc = $(range.endContainer);
        // If the selection ends in the bottom whitespace, we should act as
        // though the selection ends on the final message
        if (endc.attr('id') === "bottom_whitespace") {
            initial_end_tr = $("tr.message_row:last");
            skip_same_td_check = true;
        } else {
            initial_end_tr = $(endc.parents('tr')[0]);
        }
        end_data = find_boundary_tr(initial_end_tr, function (row) {
            return row.prev();
        });
        if (end_data === undefined) {
            return;
        }
        end_id = end_data[0];

        if (start_data[1] || end_data[1]) {
            skip_same_td_check = true;
        }

        // If the selection starts and ends in the same td,
        // we want to let the browser handle the copy-paste mostly on its own
        if (!skip_same_td_check &&
            startc.parents('td')[0] === endc.parents('td')[0]) {

            // If the user is not running the desktop app, let the browser handle
            // the copy entirely on its own
            if (window.bridge === undefined) {
                return;
            }

            // If the user is running the desktop app, we still create "div"
            // so that we can replace emoji with their text
            div.append(range.cloneContents());
        }
        else {

            // Construct a div for what we want to copy (div)
            for (row = current_msg_list.get_row(start_id);
                 rows.id(row) <= end_id;
                 row = rows.next_visible(row))
            {
                if (row.prev().hasClass("recipient_row")) {
                    content = $('<div>').text(row.prev().children(".right_part").text()
                                                .replace(/\s+/g, " ")
                                                .replace(/^\s/, "").replace(/\s$/, ""));
                    div.append($('<p>').append($('<strong>').text(content.text())));
                }

                message = current_msg_list.get(rows.id(row));

                var message_firstp = $(message.content).slice(0, 1);
                message_firstp.prepend(message.sender_full_name + ": ");
                div.append(message_firstp);
                div.append($(message.content).slice(1));
            }
        }
    }

    if (window.bridge !== undefined) {
        // If the user is running the desktop app,
        // convert emoji images to plain text for
        // copy-paste purposes.
        exports.replace_emoji_with_text(div);
    }

    // Select div so that the browser will copy it
    // instead of copying the original selection
    div.css({position: 'absolute', 'left': '-99999px'})
            .attr('id', 'copytempdiv');
    $('body').append(div);
    selection.selectAllChildren(div[0]);

    // After the copy has happened, delete the div and
    // change the selection back to the original selection
    window.setTimeout(function () {
        selection = window.getSelection();
        selection.removeAllRanges();
        _.each(ranges, function (range) {
            selection.addRange(range);
        });
        $('#copytempdiv').remove();
    },0);
}

$(function () {
    $(document).bind('copy', copy_handler);
});

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

var current_message_hover;
function message_unhover() {
    var message;
    if (current_message_hover === undefined) {
        return;
    }
    message = current_msg_list.get(rows.id(current_message_hover));
    if (message && message.sent_by_me) {
        current_message_hover.find('.message_content').find('span.edit_content').remove();
    }
    current_message_hover.removeClass('message_hovered');
    current_message_hover = undefined;
}

function message_hover(message_row) {
    var message;
    var edit_content_button = '<span class="edit_content"><i class="icon-vector-pencil edit_content_button"></i></span>';
    if (current_message_hover && message_row && current_message_hover.attr("zid") === message_row.attr("zid")) {
        return;
    }
    message = current_msg_list.get(rows.id(message_row));
    message_unhover();
    message_row.addClass('message_hovered');
    if (message && message.sent_by_me && !message.status_message && !feature_flags.disable_message_editing) {
        message_row.find('.message_content').find('p:last').append(edit_content_button);
    }
    current_message_hover = message_row;
}

exports.report_message = function (response, status_box, cls) {
    if (cls === undefined) {
        cls = 'alert';
    }

    status_box.removeClass(status_classes).addClass(cls)
              .text(response).stop(true).fadeTo(0, 1);
    status_box.show();
};

exports.report_error = function (response, xhr, status_box) {
    if (xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        response += ": " + $.parseJSON(xhr.responseText).msg;
    }

    ui.report_message(response, status_box, 'alert-error');
};

exports.report_success = function (response, status_box) {
    ui.report_message(response, status_box, 'alert-success');
};

var clicking = false;
var mouse_moved = false;

function mousedown() {
    mouse_moved = false;
    clicking = true;
}

function mousemove() {
    if (clicking) {
        mouse_moved = true;
    }
}

function need_skinny_mode() {
    if (window.matchMedia !== undefined) {
        return window.matchMedia("(max-width: 767px)").matches;
    } else {
        // IE<10 doesn't support window.matchMedia, so do this
        // as best we can without it.
        return window.innerWidth <= 767;
    }
}

function set_user_list_heights(res, usable_height, user_presences, group_pms) {
    // Calculate these heights:
    //    res.user_presences_max_height
    //    res.group_pms_max_height
    var blocks = [
        {
            real_height: user_presences.prop('scrollHeight')
        },
        {
            real_height: group_pms.prop('scrollHeight')
        }
    ];

    // The algorithm here is to give each block an amount of space proportional
    // to its size, but we don't let either block hog more than 80%.
    var sum_height = blocks[0].real_height + blocks[1].real_height;
    if (sum_height < usable_height) {
        blocks[0].max_height = blocks[0].real_height;
        blocks[1].max_height = blocks[1].real_height;
    } else {
        var ratio = (blocks[0].real_height) / sum_height;
        ratio = Math.max(0.2, ratio);
        ratio = Math.min(0.8, ratio);
        blocks[0].max_height = Math.max(40, usable_height * ratio);
        blocks[0].max_height = Math.min(blocks[0].real_height, blocks[0].max_height);

        blocks[1].max_height = usable_height - blocks[0].max_height;

        var wasted_space = blocks[1].max_height - blocks[1].real_height;
        if (wasted_space > 0) {
            blocks[0].max_height += wasted_space;
            blocks[1].max_height -= wasted_space;
        }
    }

    res.user_presences_max_height = blocks[0].max_height;
    res.group_pms_max_height = blocks[1].max_height;
}

function get_new_heights() {
    var res = {};
    var viewport_height = viewport.height();
    var top_navbar_height = $("#top_navbar").outerHeight(true);
    var invite_user_link_height = $("#invite-user-link").outerHeight(true) || 0;

    res.bottom_whitespace_height = viewport_height * 0.4;

    res.main_div_min_height = viewport_height - top_navbar_height;

    res.bottom_sidebar_height = viewport_height - top_navbar_height - 40;

    res.right_sidebar_height = viewport_height - parseInt($("#right-sidebar").css("marginTop"), 10);

    res.stream_filters_max_height =
        res.bottom_sidebar_height
        - $("#global_filters").outerHeight(true)
        - $("#streams_header").outerHeight(true)
        - 10; // stream_filters margin-bottom

    if ($("#share-the-love").is(":visible")) {
        res.stream_filters_max_height -=
            $("#share-the-love").outerHeight(true)
            + 20; // share-the-love margins + 10px of ??
    }

    // Don't let us crush the stream sidebar completely out of view
    res.stream_filters_max_height = Math.max(40, res.stream_filters_max_height);

    // RIGHT SIDEBAR
    var user_presences = $('#user_presences').expectOne();
    var group_pms = $('#group-pms').expectOne();

    var usable_height =
        res.right_sidebar_height
        - $("#feedback_section").outerHeight(true)
        - parseInt(user_presences.css("marginTop"),10)
        - parseInt(user_presences.css("marginBottom"), 10)
        - $("#userlist-header").outerHeight(true)
        - invite_user_link_height
        - parseInt(group_pms.css("marginTop"),10)
        - parseInt(group_pms.css("marginBottom"), 10)
        - $("#group-pm-header").outerHeight(true);

    // set these
    // res.user_presences_max_height
    // res.group_pms_max_height
    set_user_list_heights(
        res,
        usable_height,
        user_presences,
        group_pms
    );

    return res;
}

function left_userlist_get_new_heights() {

    var res = {};
    var viewport_height = viewport.height();
    var viewport_width = viewport.width();
    var top_navbar_height = $(".header").outerHeight(true);
    var invite_user_link_height = $("#invite-user-link").outerHeight(true) || 0;
    var share_the_love_height = $("#share-the-love").is(":visible") ? $("#share-the-love").outerHeight(true) : 0;

    var stream_filters = $('#stream_filters').expectOne();
    var user_presences = $('#user_presences').expectOne();

    var stream_filters_real_height = stream_filters.prop("scrollHeight");
    var user_list_real_height = user_presences.prop("scrollHeight");

    res.bottom_whitespace_height = viewport_height * 0.4;

    res.main_div_min_height = viewport_height - top_navbar_height;

    res.bottom_sidebar_height = viewport_height
                                - parseInt($("#left-sidebar").css("marginTop"),10)
                                - parseInt($(".bottom_sidebar").css("marginTop"),10);


    res.total_leftlist_height = res.bottom_sidebar_height
                                - $("#global_filters").outerHeight(true)
                                - $("#streams_header").outerHeight(true)
                                - $("#userlist-header").outerHeight(true)
                                - parseInt(stream_filters.css("marginBottom"),10)
                                - parseInt(user_presences.css("marginTop"), 10)
                                - parseInt(user_presences.css("marginBottom"), 10)
                                - invite_user_link_height
                                - share_the_love_height
                                - 15;


    res.stream_filters_max_height = Math.max(40, res.total_leftlist_height / 2);


    res.user_presences_max_height = Math.max(40, res.total_leftlist_height / 2);


    if (res.stream_filters_max_height > stream_filters_real_height) {
        res.stream_filters_max_height = stream_filters_real_height;
        res.user_presences_max_height = Math.max(40, res.total_leftlist_height
                                                     - stream_filters_real_height);
    }

    else if (res.user_presences_max_height > user_list_real_height) {
        res.user_presences_max_height = user_list_real_height;
        res.stream_filters_max_height = Math.max (40, res.total_leftlist_height
                                                       - user_list_real_height);
    }


    res.viewport_height = viewport_height;
    res.viewport_width = viewport_width;

    res.group_pms_max_height = 0;

    return res;
}

exports.resize_page_components = function () {
    var composebox = $("#compose");
    var floating_recipient_bar = $("#floating_recipient_bar");
    var tab_bar = $("#tab_bar");
    var tab_bar_under = $("#tab_bar_underpadding");
    var desired_width;
    if (exports.home_tab_obscured() === 'other_tab') {
        desired_width = $("div.tab-pane.active").outerWidth();
    } else {
        desired_width = $("#main_div").outerWidth();
    }
    tab_bar.width(desired_width);
    tab_bar_under.width(desired_width);

    var h;
    var sidebar;

    if (viewport.width() < 975 && feature_flags.left_side_userlist && !narrow_window) {
        narrow_window = true;
        popovers.set_userlist_placement("left");
        sidebar = $(".bottom_sidebar").expectOne();
        sidebar.append($("#user-list").expectOne());
        sidebar.append($("#group-pm-list").expectOne());
        sidebar.append($("#share-the-love").expectOne());
        $("#user_presences").css("margin", "0px");
        $("#group-pms").css("margin", "0px");
        $("#userlist-toggle").css("display", "none");
    }
    else if (viewport.width() > 975 && feature_flags.left_side_userlist && narrow_window) {
        narrow_window = false;
        popovers.set_userlist_placement("right");
        sidebar = $("#right-sidebar").expectOne();
        sidebar.append($("#user-list").expectOne());
        sidebar.append($("#group-pm-list").expectOne());
        $("#user_presences").css("margin", '');
        $("#group-pms").css("margin", '');
        $("#userlist-toggle").css("display", '');
    }


    h = narrow_window ? left_userlist_get_new_heights() : get_new_heights();

    $("#bottom_whitespace").height(h.bottom_whitespace_height);
    $("#stream_filters").css('max-height', h.stream_filters_max_height);
    $("#user_presences").css('max-height', h.user_presences_max_height);
    $("#group-pms").css('max-height', h.group_pms_max_height);
};

function resizehandler(e) {
    popovers.hide_all();
    exports.resize_page_components();

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (current_msg_list.selected_id() !== -1) {
        scroll_to_selected();
    }

    // When the screen resizes, it can make it so that messages are
    // now on the page, so we need to update the notifications bar.
    // We may want to do more here in terms of updating unread counts,
    // but it's possible that resize events can happen as part of
    // screen resolution changes, so we might want to wait for a more
    // intentional action to say that the user has "read" a message.
    var res = unread.get_counts();
    notifications_bar.update(res.home_unread_messages);
}

var is_floating_recipient_bar_showing = false;

function show_floating_recipient_bar() {
    if (!is_floating_recipient_bar_showing) {
        $("#floating_recipient_bar").css('visibility', 'visible');
        is_floating_recipient_bar_showing = true;
    }
}

var old_label;
function replace_floating_recipient_bar(desired_label) {
    var new_label, other_label, header;
    if (desired_label !== old_label) {
        if (desired_label.children(".message_header_stream").length !== 0) {
            new_label = $("#current_label_stream");
            other_label = $("#current_label_private_message");
            header = desired_label.children(".message_header_stream.right_part");

            $("#current_label_stream td:first").css(
                "background-color",
                desired_label.children(".message_header_colorblock")
                             .css("background-color"));
        } else {
            new_label = $("#current_label_private_message");
            other_label = $("#current_label_stream");
            header = desired_label.children(".message_header_private_message.right_part");
        }
        new_label.find("td:last").replaceWith(header.clone());
        other_label.css('display', 'none');
        new_label.css('display', 'table-row');
        new_label.attr("zid", rows.id(desired_label));

        new_label.toggleClass('faded', desired_label.hasClass('faded'));
        old_label = desired_label;
    }
    show_floating_recipient_bar();
}

function hide_floating_recipient_bar() {
    if (is_floating_recipient_bar_showing) {
        $("#floating_recipient_bar").css('visibility', 'hidden');
        is_floating_recipient_bar_showing = false;
    }
}

exports.update_floating_recipient_bar = function () {
    var floating_recipient_bar = $("#floating_recipient_bar");
    var floating_recipient_bar_top = floating_recipient_bar.offset().top;
    var floating_recipient_bar_bottom = floating_recipient_bar_top + floating_recipient_bar.outerHeight();

    // Find the last message where the top of the recipient
    // row is at least partially occluded by our box.
    // Start with the pointer's current location.
    var candidate = current_msg_list.selected_row();
    if (candidate === undefined) {
        return;
    }
    while (true) {
        candidate = candidate.prev();
        if (candidate.length === 0) {
            // We're at the top of the page and no labels are above us.
            hide_floating_recipient_bar();
            return;
        }
        if (candidate.is(".focused_table .recipient_row")) {
            if (candidate.offset().top < floating_recipient_bar_bottom) {
                break;
            }
        }
    }
    var current_label = candidate;

    // We now know what the floating stream/subject bar should say.
    // Do we show it?

    // Hide if the bottom of our floating stream/subject label is not
    // lower than the bottom of current_label (since that means we're
    // covering up a label that already exists).
    if (floating_recipient_bar_bottom <=
        (current_label.offset().top + current_label.outerHeight())) {
        hide_floating_recipient_bar();
        return;
    }

    // Hide if our bottom is in our bookend (or one bookend-height
    // above it). This means we're not showing any useful part of the
    // message above us, so why bother showing the label?
    var current_bookend = current_label.nextUntil(".bookend_tr")
                                       .andSelf()
                                       .next(".bookend_tr:first");
    // (The last message currently doesn't have a bookend, which is why this might be 0).
    if (current_bookend.length > 0) {
        if (floating_recipient_bar_bottom >
            (current_bookend.offset().top - current_bookend.outerHeight())) {
            hide_floating_recipient_bar();
            return;
        }
    }

    replace_floating_recipient_bar(current_label);
};

function hack_for_floating_recipient_bar() {
    // So, as of this writing, Firefox respects visibility: collapse,
    // but WebKit does not (at least, my Chrome doesn't.)  Instead it
    // renders it basically as visibility: hidden, which leaves a
    // slight gap that our messages peek through as they scroll
    // by. This hack fixes this by programmatically measuring how big
    // the gap is, and then moving our table up to compensate.
    var gap = $("#floating_recipient_layout_row").outerHeight(true);
    var floating_recipient = $(".floating_recipient");
    var offset = floating_recipient.offset();
    offset.top = offset.top - gap;
    floating_recipient.offset(offset);
}

function update_message_flag(messages, flag_name, set_flag) {
    $.ajax({
        type: 'POST',
        url: '/json/update_message_flags',
        data: {messages: JSON.stringify(_.pluck(messages, 'id')),
               op: set_flag ? 'add' : 'remove',
               flag: flag_name},
        dataType: 'json'});
}

function change_message_collapse(message, collapsed) {
    update_message_flag([message], "collapsed", collapsed);
}

function change_message_star(message, starred) {
    update_message_flag([message], "starred", starred);
}

function toggle_star(row_id) {
    // Update the message object pointed to by the various message
    // lists.
    var message = current_msg_list.get(row_id);

    mark_message_as_read(message);

    message.starred = message.starred !== true;

    // Avoid a full re-render, but update the star in each message
    // table in which it is visible.
    _.each([all_msg_list, home_msg_list, narrowed_msg_list], function (list) {
        if (list === undefined) {
            return;
        }
        var row = list.get_row(row_id);
        if (row === undefined) {
            // The row may not exist, e.g. if you star a message in the all
            // messages table from a stream that isn't in your home view.
            return;
        }
        var favorite_image = row.find(".message_star");
        favorite_image.toggleClass("icon-vector-star").toggleClass("icon-vector-star-empty").toggleClass("empty-star");
        var title_state = message.starred ? "Unstar" : "Star";
        favorite_image.attr("title", title_state + " this message");
    });

    // Save the star change.
    change_message_star(message, message.starred);
}

exports.small_avatar_url = function (message) {
    // Try to call this function in all places where we need 25px
    // avatar images, so that the browser can help
    // us avoid unnecessary network trips.  (For user-uploaded avatars,
    // the s=25 parameter is essentially ignored, but it's harmless.)
    //
    // We actually request these at s=50, so that we look better
    // on retina displays.
    if (message.avatar_url) {
        var url = message.avatar_url + "&s=50";
        if (message.sent_by_me) {
            url += "&stamp=" + settings.avatar_stamp;
        }
        return url;
    } else {
        return "";
    }
};

var loading_more_messages_indicator_showing = false;
exports.show_loading_more_messages_indicator = function () {
    if (! loading_more_messages_indicator_showing) {
        util.make_loading_indicator($('#loading_more_messages_indicator'),
                                    {abs_positioned: true});
        loading_more_messages_indicator_showing = true;
        hide_floating_recipient_bar();
    }
};

exports.hide_loading_more_messages_indicator = function () {
    if (loading_more_messages_indicator_showing) {
        util.destroy_loading_indicator($("#loading_more_messages_indicator"));
        loading_more_messages_indicator_showing = false;
    }
};

function show_more_link(row) {
    row.find(".message_condenser").hide();
    row.find(".message_expander").show();
}

function show_condense_link(row) {
    row.find(".message_expander").hide();
    row.find(".message_condenser").show();
}

function condense(row) {
    var content = row.find(".message_content");
    content.addClass("condensed");
    show_more_link(row);
}

function uncondense(row) {
    var content = row.find(".message_content");
    content.removeClass("condensed");
    show_condense_link(row);
}

exports.uncollapse = function (row) {
    // Uncollapse a message, restoring the condensed message [More] or
    // [Condense] link if necessary.
    var message = current_msg_list.get(rows.id(row));
    var content = row.find(".message_content");
    message.collapsed = false;
    content.removeClass("collapsed");
    change_message_collapse(message, false);

    if (message.condensed === true) {
        // This message was condensed by the user, so re-show the
        // [More] link.
        condense(row);
    } else if (message.condensed === false) {
        // This message was un-condensed by the user, so re-show the
        // [Condense] link.
        uncondense(row);
    } else if (content.hasClass("could-be-condensed")) {
        // By default, condense a long message.
        condense(row);
    } else {
        // This was a short message, no more need for a [More] link.
        row.find(".message_expander").hide();
    }
};

exports.collapse = function (row) {
    // Collapse a message, hiding the condensed message [More] or
    // [Condense] link if necessary.
    var message = current_msg_list.get(rows.id(row));
    message.collapsed = true;
    change_message_collapse(message, true);
    row.find(".message_content").addClass("collapsed");
    show_more_link(row);
};

exports.expand_summary_row = function (row) {
    var message_ids = row.attr('data-messages').split(' ');
    var messages = _.map(message_ids, function (id) {
        return current_msg_list.get(id);
    });

    _.each(messages, function (msg){
        msg.flags = _.without(msg.flags, 'force_collapse');
        msg.flags.push('force_expand');
    });
    update_message_flag(messages, 'force_expand', true);
    update_message_flag(messages, 'force_collapse', false);


    //TODO: Avoid a full re-render
    home_msg_list.rerender();
    if (current_msg_list !== home_msg_list) {
        current_msg_list.rerender();
    }

    current_msg_list.select_id(message_ids[0]);
};

exports.collapse_recipient_group = function (row) {
    var message_ids = row.attr('data-messages').split(',');
    var messages = _.map(message_ids, function (id) {
        return all_msg_list.get(id);
    });

    _.each(messages, function (msg){
        msg.flags = _.without(msg.flags, 'force_expand');
        msg.flags.push('force_collapse');
    });
    update_message_flag(messages, 'force_collapse', true);
    update_message_flag(messages, 'force_expand', false);

    //TODO: Avoid a full re-render
    home_msg_list.rerender();
    if (current_msg_list !== home_msg_list) {
        current_msg_list.rerender();
    }

    current_msg_list.select_id(message_ids[0]);
};

/* EXPERIMENTS */

/* This method allows an advanced user to use the console
 * to switch to a different pair of backgrounds for home
 * view and narrowed view. It either defaults to a specific
 * pair of colors, or allows the user to specify them.
 */
exports.switchBackground = function (homecolor, narrowcolor) {
    homecolor = homecolor || "#ffffff";
    narrowcolor = narrowcolor || "#effcff";
    $("#white-background-style").remove();
    $('head').append('<style id="white-background-style" type="text/css">' +
                         'body, #tab_bar, #tab_bar_underpadding, .message_list, #compose-container {' +
                            'background-color: ' + homecolor + '; }' +
                         'body.narrowed_view, .narrowed_view #tab_bar, .narrowed_view #tab_bar_underpadding,' +
                         '.narrowed_view .message_list, .narrowed_view #compose-container {' +
                            'background-color: ' + narrowcolor + '; }' +
                       '</style>');
    return ("Background has been changed");
};

/* This method allows an advanced user to use the console
 * to switch the application to span full width of the browser.
 */
exports.switchToFullWidth = function () {
    $("#full-width-style").remove();
    $('head').append('<style id="full-width-style" type="text/css">' +
                         '#home .alert-bar, .recipient-bar-content, #compose-container, .app-main, .header-main { max-width: none; }' +
                     '</style>');
    return ("Switched to full width");
};

/* END OF EXPERIMENTS */

$(function () {
    // NB: This just binds to current elements, and won't bind to elements
    // created after ready() is called.
    $('#send-status .send-status-close').click(
        function () { $('#send-status').stop(true).fadeOut(500); }
    );

    var throttled_mousewheelhandler = $.throttle(50, function (e, delta) {
        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.

        if (delta > 0) {
            if (viewport.at_top()) {
                navigate.up();
            }
        } else if (delta < 0) {
            if (viewport.at_bottom()) {
                navigate.down();
            }
        }

        last_viewport_movement_direction = delta;
    });

    $(window).mousewheel(function (e, delta) {
        // Ignore mousewheel events if a modal is visible.  It's weird if the
        // user can scroll the main view by wheeling over the greyed-out area.
        // Similarly, ignore events on settings page etc.
        //
        // We don't handle the compose box here, because it *should* work to
        // select the compose box and then wheel over the message stream.
        var obscured = exports.home_tab_obscured();
        if (!obscured) {
            throttled_mousewheelhandler(e, delta);
        } else if (obscured === 'modal') {
            // The modal itself has a handler invoked before this one (see below).
            // preventDefault here so that the tab behind the modal doesn't scroll.
            //
            // This needs to include the events that would be ignored by throttling.
            // That's why this code can't be moved into throttled_mousewheelhandler.
            e.preventDefault();
        }
        // If on another tab, we neither handle the event nor preventDefault, allowing
        // the tab to scroll normally.
    });

    $(window).resize($.throttle(50, resizehandler));

    // Scrolling in modals, input boxes, and other elements that
    // explicitly scroll should not scroll the main view.  Stop
    // propagation in all cases.  Also, ignore the event if the
    // element is already at the top or bottom.  Otherwise we get a
    // new scroll event on the parent (?).
    $('.modal-body, .scrolling_list, input, textarea').mousewheel(function (e, delta) {
        var self = $(this);
        var scroll = self.scrollTop();

        // The -1 fudge factor is important here due to rounding errors.  Better
        // to err on the side of not scrolling.
        var max_scroll = this.scrollHeight - self.innerHeight() - 1;

        e.stopPropagation();
        if (   ((delta > 0) && (scroll <= 0))
            || ((delta < 0) && (scroll >= max_scroll))) {
            e.preventDefault();
        }
    });

    // Ignore wheel events in the compose area which weren't already handled above.
    $('#compose').mousewheel(function (e) {
        e.stopPropagation();
        e.preventDefault();
    });

    function clear_password_change() {
        // Clear the password boxes so that passwords don't linger in the DOM
        // for an XSS attacker to find.
        $('#old_password, #new_password, #confirm_password').val('');
    }

    $('#gear-menu a[data-toggle="tab"]').on('show', function (e) {
        // Save the position of our old tab away, before we switch
        var old_tab = $(e.relatedTarget).attr('href');
        scroll_positions[old_tab] = viewport.scrollTop();
    });
    $('#gear-menu a[data-toggle="tab"]').on('shown', function (e) {
        var target_tab = $(e.target).attr('href');

        // Hide all our error messages when switching tabs
        $('.alert-error').hide();
        $('.alert-success').hide();
        $('.alert-info').hide();
        $('.alert').hide();

        $("#api_key_value").text("");
        $("#get_api_key_box").hide();
        $("#show_api_key_box").hide();
        $("#api_key_button_box").show();

        clear_password_change();

        // Set the URL bar title to show the sub-page you're currently on.
        var browser_url = target_tab;
        if (browser_url === "#home") {
            browser_url = "";
        }
        hashchange.changehash(browser_url);

        // After we show the new tab, restore its old scroll position
        // (we apparently have to do this after setting the hash,
        // because otherwise that action may scroll us somewhere.)
        if (scroll_positions.hasOwnProperty(target_tab)) {
            viewport.scrollTop(scroll_positions[target_tab]);
        } else {
            if (target_tab === '#home') {
                scroll_to_selected();
            } else {
                viewport.scrollTop(0);
            }
        }
    });

    var subs_link = $('#gear-menu a[href="#subscriptions"]');

    // If the streams page is shown by clicking directly on the "Streams"
    // link (in the gear menu), then focus the new stream textbox.
    subs_link.on('click', function (e) {
        $(document).one('subs_page_loaded.zulip', function (e) {
            $('#create_stream_name').focus().select();
        });
    });

    // Whenever the streams page comes up (from anywhere), populate it.
    subs_link.on('shown', subs.setup_page);

    var admin_link = $('#gear-menu a[href="#administration"]');
    admin_link.on('shown', admin.setup_page);

    $('#pw_change_link').on('click', function (e) {
        e.preventDefault();
        $('#pw_change_link').hide();
        $('#pw_change_controls').show();
    });

    $('#new_password').on('change keyup', function () {
        password_quality($('#new_password').val(), $('#pw_strength .bar'));
    });

    var settings_status = $('#settings-status').expectOne();
    var notify_settings_status = $('#notify-settings-status').expectOne();

    function settings_change_error(message) {
        // Scroll to the top so the error message is visible.
        // We would scroll anyway if we end up submitting the form.
        viewport.scrollTop(0);
        settings_status.removeClass(status_classes)
            .addClass('alert-error')
            .text(message).stop(true).fadeTo(0,1);
    }

    $("form.your-account-settings").expectOne().ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function (arr, form, options) {
            if (page_params.password_auth_enabled !== false) {
                // FIXME: Check that the two password fields match
                // FIXME: Use the same jQuery validation plugin as the signup form?
                var new_pw = $('#new_password').val();
                if (new_pw !== '') {
                    var password_ok = password_quality(new_pw);
                    if (password_ok === undefined) {
                        // zxcvbn.js didn't load, for whatever reason.
                        settings_change_error(
                            'An internal error occurred; try reloading the page. ' +
                            'Sorry for the trouble!');
                        return false;
                    } else if (!password_ok) {
                        settings_change_error('New password is too weak');
                        return false;
                    }
                }
            }
            return true;
        },
        success: function (resp, statusText, xhr, form) {
            var message = "Updated settings!";
            var result = $.parseJSON(xhr.responseText);

            settings_status.removeClass(status_classes)
                .addClass('alert-success')
                .text(message).stop(true).fadeTo(0,1);
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error changing settings";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            settings_change_error(response);
        },
        complete: function (xhr, statusText) {
            // Whether successful or not, clear the password boxes.
            // TODO: Clear these earlier, while the request is still pending.
            clear_password_change();
        }
    });

    $("form.notify-settings").expectOne().ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.

        success: function (resp, statusText, xhr, form) {
            var message = "Updated notification settings!";
            var result = $.parseJSON(xhr.responseText);

            if (result.enable_desktop_notifications !== undefined) {
                page_params.desktop_notifications_enabled = result.enable_desktop_notifications;
            }
            if (result.enable_sounds !== undefined) {
                page_params.sounds_enabled = result.enable_sounds;
            }

            if (result.enable_offline_email_notifications !== undefined) {
                page_params.enable_offline_email_notifications = result.enable_offline_email_notifications;
            }

            if (result.enable_offline_push_notifications !== undefined) {
                page_params.enable_offline_push_notifications = result.enable_offline_push_notifications;
            }

            if (result.enable_digest_emails !== undefined) {
                page_params.enable_digest_emails = result.enable_digest_emails;
            }

            notify_settings_status.removeClass(status_classes)
                .addClass('alert-success')
                .text(message).stop(true).fadeTo(0,1);
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error changing settings";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }

            notify_settings_status.removeClass(status_classes)
                .addClass('alert-error')
                .text(response).stop(true).fadeTo(0,1);
        }
    });

    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#get_api_key_box form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var message = "Updated settings!";
            var result = $.parseJSON(xhr.responseText);
            $("#get_api_key_password").val("");
            $("#api_key_value").text(result.api_key);
            $("#show_api_key_box").show();
            $("#get_api_key_box").hide();
            settings_status.hide();
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error getting API key";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-error')
                .text(response).stop(true).fadeTo(0,1);
            $("#show_api_key_box").hide();
            $("#get_api_key_box").show();
        }
    });

    // A little hackish, because it doesn't seem to totally get us the
    // exact right width for the floating_recipient_bar and compose
    // box, but, close enough for now.
    resizehandler();
    hack_for_floating_recipient_bar();

    if (!feature_flags.left_side_userlist) {
        $("#navbar-buttons").addClass("right-userlist");
    }

    if (feature_flags.summarize_read_while_narrowed) {
        $("#main_div").on("click", ".summary_row  .messages-expand", function (e) {
            exports.expand_summary_row($(e.target).closest('.summary_row').expectOne());
            e.stopImmediatePropagation();
        });
        $("#main_div").on("click", ".recipient_row .messages-collapse", function (e) {
            exports.collapse_recipient_group($(e.target).closest('.recipient_row').expectOne());
            e.stopImmediatePropagation();
        });
    }

    function is_clickable_message_element(target) {
        return target.is("a") || target.is("img.message_inline_image") || target.is("img.twitter-avatar") ||
            target.is("div.message_length_controller") || target.is("textarea") || target.is("input") ||
            target.is("i.edit_content_button");
    }

    $("#main_div").on("click", ".messagebox", function (e) {
        if (is_clickable_message_element($(e.target))) {
            // If this click came from a hyperlink, don't trigger the
            // reply action.  The simple way of doing this is simply
            // to call e.stopPropagation() from within the link's
            // click handler.
            //
            // Unfortunately, on Firefox, this breaks Ctrl-click and
            // Shift-click, because those are (apparently) implemented
            // by adding an event listener on link clicks, and
            // stopPropagation prevents them from being called.
            return;
        }
        if (!(clicking && mouse_moved)) {
            // Was a click (not a click-and-drag).
            var row = $(this).closest(".message_row");
            var id = rows.id(row);

            if (message_edit.is_editing(id)) {
                // Clicks on a message being edited shouldn't trigger a reply.
                return;
            }

            current_msg_list.select_id(id);
            respond_to_message({trigger: 'message click'});
            e.stopPropagation();
            popovers.hide_all();
        }
        mouse_moved = false;
        clicking = false;
    });

    $("#main_div").on("mousedown", ".messagebox", mousedown);
    $("#main_div").on("mousemove", ".messagebox", mousemove);
    $("#main_div").on("mouseover", ".message_row", function (e) {
        var row = $(this).closest(".message_row");
        message_hover(row);
    });

    $("#main_div").on("mouseleave", ".message_row", function (e) {
        message_unhover();
    });

    $("#main_div").on("mouseover", ".message_sender", function (e) {
        var row = $(this).closest(".message_row");
        row.addClass("sender_name_hovered");
    });

    $("#main_div").on("mouseout", ".message_sender", function (e) {
        var row = $(this).closest(".message_row");
        row.removeClass("sender_name_hovered");
    });

    $("#main_div").on("click", ".star", function (e) {
        e.stopPropagation();
        popovers.hide_all();
        toggle_star(rows.id($(this).closest(".message_row")));
    });

    $("#home").on("click", ".message_expander", function (e) {
        // Expanding a message can mean either uncollapsing or
        // uncondensing it.
        var row = $(this).closest(".message_row");
        var message = current_msg_list.get(rows.id(row));
        var content = row.find(".message_content");
        if (message.collapsed) {
            // Uncollapse.
            ui.uncollapse(row);
        } else if (content.hasClass("could-be-condensed")) {
            // Uncondense (show the full long message).
            message.condensed = false;
            content.removeClass("condensed");
            $(this).hide();
            row.find(".message_condenser").show();
        }
    });

    $("#home").on("click", ".message_condenser", function (e) {
        var row = $(this).closest(".message_row");
        current_msg_list.get(rows.id(row)).condensed = true;
        condense(row);
    });

    function get_row_id_for_narrowing(narrow_link_elem) {
        var row = rows.get_closest_row(narrow_link_elem);

        var nearest = current_msg_list.get(rows.id(row));
        var selected = current_msg_list.selected_message();
        if (util.same_recipient(nearest, selected)) {
            return selected.id;
        } else {
            return nearest.id;
        }
    }

    $("#home").on("click", ".narrows_by_recipient", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        var row_id = get_row_id_for_narrowing(this);
        narrow.by_recipient(row_id, {trigger: 'message header'});
    });

    $("#home").on("click", ".narrows_by_subject", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        var row_id = get_row_id_for_narrowing(this);
        narrow.by_subject(row_id, {trigger: 'message header'});
    });

    $("#userlist-toggle-button").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var sidebarHidden = !$(".app-main .column-right").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            popovers.show_userlist_sidebar();
        }
    });

    $("#streamlist-toggle-button").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var sidebarHidden = !$(".app-main .column-left").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            popovers.show_streamlist_sidebar();
        }
    });

    $("#subscriptions_table").on("mouseover", ".subscription_header", function (e) {
        $(this).addClass("active");
    });

    $("#subscriptions_table").on("mouseout", ".subscription_header", function (e) {
        $(this).removeClass("active");
    });

    $("#stream").on('blur', function () { compose.decorate_stream_bar(this.value); });

    // Capture both the left-sidebar Home click and the tab breadcrumb Home
    $(document).on('click', "li[data-name='home']", function (e) {
        ui.change_tab_to('#home');
        narrow.deactivate();
        // We need to maybe scroll to the selected message
        // once we have the proper viewport set up
        setTimeout(maybe_scroll_to_selected, 0);
        e.preventDefault();
    });

    $(".brand").on('click', function (e) {
        if (exports.home_tab_obscured()) {
            ui.change_tab_to('#home');
        } else {
            narrow.restore_home_state();
        }
        maybe_scroll_to_selected();
        e.preventDefault();
    });

    $(window).on('blur', function () {
        $(document.body).addClass('window_blurred');
    });

    $(window).on('focus', function () {
        $(document.body).removeClass('window_blurred');
    });

    $(document).on('message_selected.zulip', function (event) {
        if (current_msg_list !== event.msg_list) {
            return;
        }
        if (event.id === -1) {
            // If the message list is empty, don't do anything
            return;
        }
        var row = event.msg_list.get_row(event.id);
        $('.selected_message').removeClass('selected_message');
        row.addClass('selected_message');

        if (event.then_scroll) {
            if (row.length === 0) {
                blueslip.debug("message_selected missing selected row", {
                    previously_selected: event.previously_selected,
                    selected_id: event.id,
                    selected_idx: event.msg_list.selected_idx(),
                    selected_idx_exact: event.msg_list._items.indexOf(event.msg_list.get(event.id)),
                    render_start: event.msg_list.view._render_win_start,
                    render_end: event.msg_list.view._render_win_end
                });
            }

            // Scroll to place the message within the current view;
            // but if this is the initial placement of the pointer,
            // just place it in the very center
            recenter_view(row, {from_scroll: event.from_scroll,
                                force_center: event.previously_selected === -1});
        }
    });

    $("#main_div").on("mouseenter", ".message_time", function (e) {
        var time_elem = $(e.target);
        var row = time_elem.closest(".message_row");
        var message = current_msg_list.get(rows.id(row));
        timerender.set_full_datetime(message, time_elem);
    });

    $('#user_presences').expectOne().on('click', '.selectable_sidebar_block', function (e) {
        var email = $(e.target).parents('li').attr('data-email');
        narrow.by('pm-with', email, {select_first_unread: true, trigger: 'sidebar'});
        // The preventDefault is necessary so that clicking the
        // link doesn't jump us to the top of the page.
        e.preventDefault();
        // The stopPropagation is necessary so that we don't
        // see the following sequence of events:
        // 1. This click "opens" the composebox
        // 2. This event propagates to the body, which says "oh, hey, the
        //    composebox is open and you clicked out of it, you must want to
        //    stop composing!"
        e.stopPropagation();
        // Since we're stopping propagation we have to manually close any
        // open popovers.
        popovers.hide_all();
    });

    $('#group-pms').expectOne().on('click', '.selectable_sidebar_block', function (e) {
        var emails = $(e.target).parents('li').attr('data-emails');
        narrow.by('pm-with', emails, {select_first_unread: true, trigger: 'sidebar'});
        e.preventDefault();
        e.stopPropagation();
        popovers.hide_all();
    });

    $('#streams_inline_cog').tooltip({ placement: 'left',
                                       animation: false });

    $('#streams_header a').click(function (e) {
        exports.change_tab_to('#subscriptions');

        e.preventDefault();
    });

    popovers.register_click_handlers();
    notifications.register_click_handlers();

    $('.compose_stream_button').click(function (e) {
        compose.start('stream');
    });
    $('.compose_private_button').click(function (e) {
        compose.start('private');
    });

    $('.empty_feed_compose_stream').click(function (e) {
        compose.start('stream', {trigger: 'empty feed message'});
        e.preventDefault();
    });
    $('.empty_feed_compose_private').click(function (e) {
        compose.start('private', {trigger: 'empty feed message'});
        e.preventDefault();
    });
    $('.empty_feed_join').click(function (e) {
        subs.show_and_focus_on_narrow();
        e.preventDefault();
    });

    // Keep these 2 feedback bot triggers separate because they have to
    // propagate the event differently.
    $('.feedback').click(function (e) {
        compose.start('private', { 'private_message_recipient': 'feedback@zulip.com',
                                   trigger: 'feedback menu item' });

    });
    $('#feedback_button').click(function (e) {
        e.stopPropagation();
        popovers.hide_all();
        compose.start('private', { 'private_message_recipient': 'feedback@zulip.com',
                                   trigger: 'feedback button' });

    });
    $('.logout_button').click(function (e) {
        $('#logout_form').submit();
    });
    $('.restart_get_updates_button').click(function (e) {
        restart_get_updates({dont_block: true});
    });

    $('#api_key_button').click(function (e) {
        if (page_params.password_auth_enabled !== false) {
            $("#get_api_key_box").show();
        } else {
            // Skip the password prompt step
            $("#get_api_key_box form").submit();
        }
        $("#api_key_button_box").hide();
    });

    var notification_docs = $("#notification-docs");
    notification_docs.popover({"placement": "right",
                               "content": templates.render('notification_docs', {}),
                               "trigger": "manual"});
    $("body").on("mouseover", "#notification-docs", function (e) {
        notification_docs.popover('show');
        e.stopPropagation();
    });
    $("body").on("mouseout", "#notification-docs", function (e) {
        notification_docs.popover('hide');
        e.stopPropagation();
    });

    $('body').on('click', '.edit_content_button', function (e) {
        var row = current_msg_list.get_row(rows.id($(this).closest(".message_row")));
        message_edit.start(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $('body').on('click','.always_visible_topic_edit,.on_hover_topic_edit', function (e) {
        var recipient_row = $(this).closest(".recipient_row");
        message_edit.start_topic_edit(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_save", function (e) {
        var recipient_row = $(this).closest(".recipient_row");
        if (message_edit.save(recipient_row) === true) {
            current_msg_list.hide_edit_topic(recipient_row);
        }
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_cancel", function (e) {
        var recipient_row = $(this).closest(".recipient_row");
        current_msg_list.hide_edit_topic(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_save", function (e) {
        var row = $(this).closest(".message_row");
        if (message_edit.save(row) === true) {
            message_edit.end(row);
        }
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_cancel", function (e) {
        var row = $(this).closest(".message_row");
        message_edit.end(row);
        e.stopPropagation();
        popovers.hide_all();
    });

    // Webathena integration code
    $('#right-sidebar, #top_navbar').on('click', '.webathena_login', function (e) {
        $("#zephyr-mirror-error").hide();
        var principal = ["zephyr", "zephyr"];
        WinChan.open({
            url: "https://webathena.mit.edu/#!request_ticket_v1",
            relay_url: "https://webathena.mit.edu/relay.html",
            params: {
                realm: "ATHENA.MIT.EDU",
                principal: principal
            }
        }, function (err, r) {
            if (err) {
                blueslip.warn(err);
                return;
            }
            if (r.status !== "OK") {
                blueslip.warn(r);
                return;
            }

            $.ajax({
                type:     'POST',
                url:      "/accounts/webathena_kerberos_login/",
                data:     {cred: JSON.stringify(r.session)},
                dataType: 'json',
                success: function (data, success) {
                    $("#zephyr-mirror-error").hide();
                },
                error: function (data, success) {
                    $("#zephyr-mirror-error").show();
                }
            });
        });
        $('#settings-dropdown').dropdown("toggle");
        e.preventDefault();
        e.stopPropagation();
    });
    // End Webathena code

    $(document).on('click', function (e) {
        if (e.button !== 0) {
            // Firefox emits right click events on the document, but not on
            // the child nodes, so the #compose stopPropagation doesn't get a
            // chance to capture right clicks.
            return;
        }

        // Dismiss popovers if the user has clicked outside them
        if ($('.popover-inner').has(e.target).length === 0) {
            popovers.hide_all();
        }

        // Unfocus our compose area if we click out of it. Don't let exits out
        // of modals or selecting text (for copy+paste) trigger cancelling.
        if (compose.composing() && !$(e.target).is("a") &&
            ($(e.target).closest(".modal").length === 0) &&
            window.getSelection().toString() === "") {
            compose.cancel();
        }
    });

    function handle_compose_click(e) {
        // Don't let clicks in the compose area count as
        // "unfocusing" our compose -- in other words, e.g.
        // clicking "Press enter to send" should not
        // trigger the composebox-closing code above.
        // But do allow our formatting link.
        if (!$(e.target).is("a")) {
            e.stopPropagation();
        }
        // Still hide the popovers, however
        popovers.hide_all();
    }

    $("#compose_buttons").click(handle_compose_click);
    $(".compose-content").click(handle_compose_click);

    $("#compose_close").click(function (e) {
        compose.cancel();
    });

    $(".bankruptcy_button").click(function (e) {
        enable_unread_counts();
    });

    $('#yes-bankrupt').click(function (e) {
        fast_forward_pointer();
        $("#yes-bankrupt").hide();
        $("#no-bankrupt").hide();
        $(this).after($("<div>").addClass("alert alert-info settings_committed")
               .text("Bringing you to your latest messages…"));
    });

    if (feature_flags.disable_message_editing) {
        $("#edit-message-hotkey-help").hide();
    }

    // Some MIT-specific customizations
    if (page_params.domain === 'mit.edu') {
        $("#user-list").hide();
        $("#group-pm-list").hide();
    }

    // UI experiments
    if (feature_flags.experimental_background) {
        exports.switchBackground();
    }

    if (feature_flags.full_width) {
        exports.switchToFullWidth();
    }

    // initialize other stuff
    composebox_typeahead.initialize();
    search.initialize();
    notifications.initialize();
    hashchange.initialize();
    invite.initialize();
    activity.initialize();
    tutorial.initialize();
});


var scroll_start_message;

function scroll_finished() {
    actively_scrolling = false;

    if ($('#home').hasClass('active')) {
        if (!suppress_scroll_pointer_update) {
            keep_pointer_in_view();
        } else {
            suppress_scroll_pointer_update = false;
        }
        exports.update_floating_recipient_bar();
        if (viewport.scrollTop() === 0 &&
            have_scrolled_away_from_top) {
            have_scrolled_away_from_top = false;
            load_more_messages(current_msg_list);
        } else if (!have_scrolled_away_from_top) {
            have_scrolled_away_from_top = true;
        }
        // When the window scrolls, it may cause some messages to
        // enter the screen and become read.  Calling
        // process_visible_unread_messages will update necessary
        // data structures and DOM elements.
        setTimeout(process_visible_unread_messages, 0);
    }
}

var scroll_timer;
function scroll_finish() {
    actively_scrolling = true;
    clearTimeout(scroll_timer);
    scroll_timer = setTimeout(scroll_finished, 100);
}

exports.register_scroll_handler = function () {
    $(window).scroll($.throttle(50, function (e) {
        process_visible_unread_messages();
        scroll_finish();
    }));
};

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.js).
var saved_compose_cursor = 0;

$(function () {
    $('#new_message_content').blur(function () {
        saved_compose_cursor = $(this).caret().start;
    });
});

exports.restore_compose_cursor = function () {
    // Restore as both the start and end point, i.e.
    // nothing selected.
    $('#new_message_content')
        .focus()
        .caret(saved_compose_cursor, saved_compose_cursor);
};

exports.condense_and_collapse = function (elems) {
    var height_cutoff = viewport.height() * 0.65;

    function could_be_condensed(elem) {
        return elem.getBoundingClientRect().height > height_cutoff;
    }

    _.each(elems, function (elem) {
        var content = $(elem).find(".message_content");
        var message = current_msg_list.get(rows.id($(elem)));
        if (content !== undefined && message !== undefined) {
            var long_message = could_be_condensed(elem);
            if (long_message) {
                // All long messages are flagged as such.
                content.addClass("could-be-condensed");
            }

            // If message.condensed is defined, then the user has manually
            // specified whether this message should be expanded or condensed.
            if (message.condensed === true) {
                condense($(elem));
                return;
            } else if (message.condensed === false) {
                uncondense($(elem));
                return;
            } else if (long_message) {
                // By default, condense a long message.
                condense($(elem));
            }

            // Completely hide the message and replace it with a [More]
            // link if the user has collapsed it.
            if (message.collapsed) {
                content.addClass("collapsed");
                $(elem).find(".message_expander").show();
            }
        }
    });
};

$(function () {
    // Workaround for Bootstrap issue #5900, which basically makes dropdowns
    // unclickable on mobile devices.
    // https://github.com/twitter/bootstrap/issues/5900
    $('a.dropdown-toggle, .dropdown-menu a').on('touchstart', function (e) {
        e.stopPropagation();
    });
});

$(function () {
    if (window.bridge !== undefined) {
        // Disable "spellchecking" in our desktop app. The "spellchecking"
        // in our Mac app is actually autocorrect, and frustrates our
        // users.
        $("#new_message_content").attr('spellcheck', 'false');
        // Modify the zephyr mirroring error message in our desktop
        // app, since it doesn't work from the desktop version.
        $("#webathena_login_menu").hide();
        $("#normal-zephyr-mirror-error-text").addClass("notdisplayed");
        $("#desktop-zephyr-mirror-error-text").removeClass("notdisplayed");
    }
});


return exports;
}());
