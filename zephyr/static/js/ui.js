// We want to remember how far we were scrolled on each 'tab'.
// To do so, we need to save away the old position of the
// scrollbar when we switch to a new tab (and restore it
// when we switch back.)
var scroll_positions = {};
var current_label;
var current_scroll_direction = "down";

function update_scroll_direction(delta) {
    if (delta !== undefined) {
        if (delta <= 0) {
            current_scroll_direction = "down";
        } else {
            current_scroll_direction = "up";
        }
    }
}

function register_onclick(message_row, message_id) {
    message_row.find(".messagebox").click(function (e) {
        if (!(clicking && mouse_moved)) {
            // Was a click (not a click-and-drag).
            select_message_by_id(message_id);
            respond_to_message();
        }
        mouse_moved = false;
        clicking = false;
    });
}

function focus_on(field_id) {
    // Call after autocompleting on a field, to advance the focus to
    // the next input field.

    // Bootstrap's typeahead does not expose a callback for when an
    // autocomplete selection has been made, so we have to do this
    // manually.
    $("#" + field_id).focus();
}

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

function hide_email() {
    $('.sender_email').addClass('invisible');
}

function show_email(message_id) {
    hide_email();
    get_message_row(message_id).find('.sender_email').removeClass('invisible');
}

function report_error(response, xhr, status_box) {
    if (xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        response += ": " + $.parseJSON(xhr.responseText).msg;
    }

    status_box.removeClass(status_classes).addClass('alert-error')
              .text(response).stop(true).fadeTo(0, 1);
    status_box.show();
}

function report_success(response, status_box) {
    status_box.removeClass(status_classes).addClass('alert-success')
              .text(response).stop(true).fadeTo(0, 1);
    status_box.show();
}

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

function resizehandler(e) {
    var viewport = $(window);
    var sidebar = $("#sidebar");
    var sidebar_nav = $(".sidebar-nav");
    var composebox = $("#compose");
    var narrowbox = $("#narrowbox");
    if (viewport.width() <= 767) {
        sidebar.removeClass('nav-stacked');

        var space_taken_up_by_navbar = sidebar_nav.outerHeight(true);
        $("#nav_whitespace").height(space_taken_up_by_navbar); // .visible-phone only, so doesn't need undoing
        narrowbox.css('top', space_taken_up_by_navbar);

        var message_list_width = $("#main_div").outerWidth();
        composebox.width(message_list_width);
        narrowbox.width(message_list_width);
        sidebar_nav.width(message_list_width);
    } else {
        sidebar.addClass('nav-stacked');
        narrowbox.css('top', 0);
        narrowbox.width('');
        composebox.width('');
        sidebar_nav.width('');
    }

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (selected_message_id !== -1) {
        scroll_to_selected();
    }
}

var autocomplete_needs_update = false;

function update_autocomplete() {
    stream_list.sort();
    people_list.sort(function (x, y) {
        if (x.email === y.email) return 0;
        if (x.email < y.email) return -1;
        return 1;
    });

    var huddle_typeahead_list = $.map(people_list, function (person) {
        return person.full_name + " <" + person.email + ">";
    });

    // We need to muck with the internal state of Typeahead in order to update
    // its data source
    $("#stream").data("typeahead").source = stream_list;
    $("#huddle_recipient").data("typeahead").source = huddle_typeahead_list;

    autocomplete_needs_update = false;
}

function replace_narrowbar() {
    if ($(current_label).children(".message_newstyle_stream").length !== 0) {
        $("#current_label_stream td:first").replaceWith($(current_label).children(".message_newstyle_stream").clone());
        $("#current_label_stream td:last").replaceWith($(current_label).children(".message_newstyle_subject").clone());
        $("#current_label_huddle").css('display', 'none');
        $("#current_label_stream").css('display', 'table-row');
    } else {
        $("#current_label_huddle td:first").replaceWith($(current_label).children(".message_newstyle_pm").clone());
        $("#current_label_stream").css('display', 'none');
        $("#current_label_huddle").css('display', 'table-row');
    }
}

function hide_narrowbar() {
    $("#current_label_stream").css('display', 'none');
    $("#current_label_huddle").css('display', 'none');
}

function update_fixed_narrowbar() {
    var fixed_narrowbar = $("#current_label_stream");
    var fixed_narrowbar_top = fixed_narrowbar.offset().top;
    var fixed_narrowbar_bottom = fixed_narrowbar_top + fixed_narrowbar.height();

    // The recipient row directly above the fixed_narrowbar.
    var new_label_candidate = $(".focused_table .recipient_row").filter(function () {
        return ($(this).offset().top < fixed_narrowbar_top);
    }).last();

    var bookend_cover = new_label_candidate.nextUntil(".bookend_tr").next(".bookend_tr");
    if (bookend_cover.length === 0) {
        // We have no bookends.
        return;
    }
    bookend_cover = $(bookend_cover[0]);
    var my_top = $(bookend_cover).offset().top;
    var my_bottom = my_top + bookend_cover.height();

    if (current_scroll_direction === "down") {
        if ((my_top >= fixed_narrowbar_top) &&
            (my_top < fixed_narrowbar_bottom)) {
            // The bookend has entered the space occupied by the
            // fixed_narrowbar, so hide the fixed_narrowbar.
            hide_narrowbar();
        } else if ((new_label_candidate.length !== 0) &&
                   (new_label_candidate[0] !== current_label)) {
            current_label = new_label_candidate[0];
            replace_narrowbar();
        }
    } else {
        if ((my_bottom >= fixed_narrowbar_top) &&
            (my_bottom < fixed_narrowbar_bottom)) {
            // We are scrolling up and have just reached a bookend, so hide the
            // old fixed_narrowbar for the stream below us.
            hide_narrowbar();
        } else {
            if ((my_bottom >= fixed_narrowbar_bottom) &&
                (my_bottom < fixed_narrowbar_top + fixed_narrowbar.height() * 2) &&
                (new_label_candidate.length !== 0) &&
                (new_label_candidate[0] !== current_label)) {
                // We are scrolling up and enough of the above stream is in view
                // that we should reveal the fixed_narrowbar for that stream.
                current_label = new_label_candidate[0];
                replace_narrowbar();
            }
        }
    }
}

$(function () {
    // NB: This just binds to current elements, and won't bind to elements
    // created after ready() is called.

    $('#message-type-tabs a[href="#stream-message"]').on('shown', function (e) {
        $('#personal-message').hide();
        $('#stream-message').show();
        $('#new_message_type').val('stream');
        $("#send-status").removeClass(status_classes).hide();
        focus_on("stream");
    });
    $('#message-type-tabs a[href="#personal-message"]').on('shown', function (e) {
        $('#personal-message').show();
        $('#stream-message').hide();
        $('#new_message_type').val('personal');
        $("#send-status").removeClass(status_classes).hide();
        focus_on("huddle_recipient");
    });

    // Prepare the click handler for subbing to a new stream to which
    // you have composed a message.
    $('#create-it').click(function () {
        sub_from_home(compose_stream_name(), $('#stream-dne'));
    });

    // Prepare the click handler for subbing to an existing stream.
    $('#sub-it').click(function () {
        sub_from_home(compose_stream_name(), $('#stream-nosub'));
    });

    var throttled_scrollhandler = $.throttle(50, function(e, delta) {
        if ($('#home').hasClass('active')) {
            keep_pointer_in_view();
            if (e.type === 'mousewheel') {
                // If we mousewheel (or trackpad-scroll) when
                // we're at the top and bottom of the page, the
                // pointer may still want to move.
                move_pointer_at_page_top_and_bottom();
            }
        }
        update_scroll_direction(delta);
        print_elapsed_time("update_fixed_narrowbar", update_fixed_narrowbar);
    });
    $(window).mousewheel(throttled_scrollhandler);
    $(window).scroll(throttled_scrollhandler);

    var throttled_resizehandler = $.throttle(50, resizehandler);
    $(window).resize(throttled_resizehandler);

    $('#sidebar a[data-toggle="pill"]').on('show', function (e) {
        // Save the position of our old tab away, before we switch
        var viewport = $(window);
        var old_tab = $(e.relatedTarget).attr('href');
        scroll_positions[old_tab] = viewport.scrollTop();
    });
    $('#sidebar a[data-toggle="pill"]').on('shown', function (e) {
        // Right after we show the new tab, restore its old scroll position
        var viewport = $(window);
        var target_tab = $(e.target).attr('href');
        if (scroll_positions.hasOwnProperty(target_tab)) {
            viewport.scrollTop(scroll_positions[target_tab]);
        } else {
            viewport.scrollTop(0);
        }

        // Hide all our error messages when switching tabs
        $('.alert-error').hide();
        $('.alert-success').hide();
        $('.alert-info').hide();
        $('.alert').hide();

        // Set the URL bar title to show the sub-page you're currently on.
        var browser_url = $(e.target).attr('href');
        if (browser_url === "#home") {
            browser_url = "#";
        }
        window.history.pushState("object or string", "Title", browser_url);
    });

    $('.button-slide').click(function () {
        show_compose('stream', $("#stream"));
    });

    $('#sidebar a[href="#subscriptions"]').click(fetch_subs);

    var settings_status = $('#settings-status');
    $("#current_settings form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var message = "Updated settings!";
            var result = $.parseJSON(xhr.responseText);
            if ((result.full_name !== undefined) || (result.short_name !== undefined)) {
                message = "Updated settings!  You will need to reload the page for your changes to take effect.";
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-success')
                .text(message).stop(true).fadeTo(0,1);
            // TODO: In theory we should auto-reload or something if
            // you changed the email address or other fields that show
            // up on all screens
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error changing settings";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-error')
                .text(response).stop(true).fadeTo(0,1);
        }
    });

    // A little hackish, because it doesn't seem to totally get us
    // the exact right width for the narrowbar and compose box,
    // but, close enough for now.
    resizehandler();

    // limit number of items so the list doesn't fall off the screen
    $( "#stream" ).typeahead({
        source: [], // will be set in update_autocomplete()
        items: 3
    });
    $( "#subject" ).typeahead({
        source: function (query, process) {
            var stream_name = $("#stream").val();
            if (subject_dict.hasOwnProperty(stream_name)) {
                return subject_dict[stream_name];
            }
            return [];
        },
        items: 2
    });
    $( "#huddle_recipient" ).typeahead({
        source: [], // will be set in update_autocomplete()
        items: 4,
        matcher: function (item) {
            // Assumes email addresses don't have commas or semicolons in them
            var current_recipient = $(this.query.split(/[,;] */)).last()[0];
            // Case-insensitive (from Bootstrap's default matcher).
            return (item.toLowerCase().indexOf(current_recipient.toLowerCase()) !== -1);
        },
        updater: function (item) {
            var previous_recipients = this.query.split(/[,;] */);
            previous_recipients.pop();
            previous_recipients = previous_recipients.join(", ");
            if (previous_recipients.length !== 0) {
                previous_recipients += ", ";
            }
            // Extracting the email portion via regex is icky, but the Bootstrap
            // typeahead widget doesn't seem to be flexible enough to pass
            // objects around
            var email_re = /<[^<]*>$/;
            var email = email_re.exec(item)[0];
            return previous_recipients + email.substring(1, email.length - 1) + ", ";
        }

    });

    $( "#huddle_recipient" ).blur(function (event) {
        var val = $(this).val();
        $(this).val(val.replace(/[,;] *$/, ''));
    });

    update_autocomplete();
});
