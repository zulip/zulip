/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, nomen: true, regexp: true */
/*global $: false, jQuery: false, ich: false,
    zephyr_json: false, initial_pointer: false, username: false,
    class_list: false, instance_list: false, people_list: false */

$(function () {
    $('#zephyr-type-tabs a[href="#class-message"]').on('shown', function (e) {
        $('#class-message input:not(:hidden):first').focus().select();
    });
    $('#zephyr-type-tabs a[href="#personal-message"]').on('shown', function (e) {
        $('#personal-message input:not(:hidden):first').focus().select();
    });
});

$.ajaxSetup({
    beforeSend: function (xhr, settings) {
        function getCookie(name) {
            var i, cookies, cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                cookies = document.cookie.split(';');
                for (i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            // Only send the token to relative URLs i.e. locally.
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }
});

function sub(zephyr_class) {
    // Supports multiple classes, separate by commas.
    // TODO: check the return value and handle an error condition
    $.post('/subscriptions/add/', {new_subscriptions: zephyr_class});
}

function hide_compose() {
    $('input, textarea, button').blur();
    $('.zephyr_compose').slideUp('fast');
}

function show_compose(tabname) {
    $('.zephyr_compose').slideDown('fast');
    if (tabname) {
        $('#zephyr-type-tabs a[href="#' + tabname + '-message"]').tab('show');
    }
}

$(function () {
    var status_classes = 'alert-error alert-success alert-info';
    var send_status = $('#send-status');
    var buttons = $('#class-message, #personal-message').find('input[type="submit"]');

    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function (form, _options) {
            send_status.removeClass(status_classes)
                       .addClass('alert-info')
                       .text('Sending')
                       .stop(true).fadeTo(0,1);
            hide_compose();
            buttons.attr('disabled', 'disabled');
            buttons.blur();

            if ($("#class-message:visible")[0] === undefined) {// we're not dealing with classes
                return true;
            }
            var okay = true;
            $.ajax({
                url: "subscriptions/exists/" + $("#class").val(),
                async: false,
                success: function (data) {
                    if (data === "False") {
                        // The class doesn't exist
                        okay = false;
                        send_status.removeClass(status_classes);
                        send_status.toggle();
                        $('#class-dne-name').text($("#class").val());
                        $('#class-dne').show();
                        $('#create-it').focus().click(function () {
                            sub($("#class").val());
                            $("#class-message form").ajaxSubmit();
                            $('#class-dne').stop(true).fadeOut(500);
                        });
                        buttons.removeAttr('disabled');
                    }
                }
            });
            if (okay && class_list.indexOf($("#class").val()) === -1) {
                // You're not subbed to the class
                okay = false;
                send_status.removeClass(status_classes);
                send_status.toggle();
                $('#class-nosub-name').text($("#class").val());
                $('#class-nosub').show();
                $('#sub-it').focus().click(function () {
                    sub($("#class").val());
                    $("#class-message form").ajaxSubmit();
                    $('#class-nosub').stop(true).fadeOut(500);
                });
                buttons.removeAttr('disabled');
            }
            return okay;
        },
        success: function (resp, statusText, xhr, form) {
            form.find('textarea').val('');
            send_status.removeClass(status_classes)
                       .addClass('alert-success')
                       .text('Sent message')
                       .stop(true).fadeTo(0,1).delay(1000).fadeOut(1000);
            buttons.removeAttr('disabled');
            clear_compose_box();
        },
        error: function (xhr) {
            var response = "Error sending message";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            send_status.removeClass(status_classes)
                       .addClass('alert-error')
                       .text(response)
                       .append($('<span />')
                           .addClass('send-status-close').html('&times;')
                           .click(function () { send_status.stop(true).fadeOut(500); }))
                       .stop(true).fadeTo(0,1);

            buttons.removeAttr('disabled');
        }
    };

    send_status.hide();
    $("#class-message form").ajaxForm(options);
    $("#personal-message form").ajaxForm(options);
});

var selected_zephyr_id = 0;  /* to be filled in on document.ready */
var last_received = -1;

function get_all_zephyr_rows() {
    return $('tr.zephyr_row');
}

function get_next_visible(zephyr_row) {
    return zephyr_row.nextAll(':visible:first');
}

function get_prev_visible(zephyr_row) {
    return zephyr_row.prevAll(':visible:first');
}

function get_id(zephyr_row) {
    return zephyr_row.attr('id');
}

function get_zephyr(zephyr_id) {
    return $("#" + zephyr_id);
}

function scroll_to_selected() {
    var main_div = $('#main_div');
    main_div.scrollTop(0);
    main_div.scrollTop(get_zephyr(selected_zephyr_id).offset().top - main_div.height()/1.5);
}

function respond_to_zephyr() {
    var parent, zephyr;
    var recipient, recipients;
    parent = get_zephyr(selected_zephyr_id);
    zephyr = zephyr_dict[parent.attr('id')];

    $('.zephyr_compose').slideToggle('fast');

    if (zephyr.type === 'class') {
        $('#zephyr-type-tabs a[href="#class-message"]').tab('show');
        $("#class").val(zephyr.display_recipient);
        $("#instance").val(zephyr.instance);
        $("#new_zephyr").focus();
        $("#new_zephyr").select();
    } else if (zephyr.type === 'huddle') {
        $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
        recipient = '';
        for (i in  zephyr.display_recipient) {
            recipient += zephyr.display_recipient[i].name + ', ';
        }
        $("#recipient").val(recipient);
        $("#new_personal_zephyr").focus();
        $("#new_personal_zephyr").select();
    } else if (zephyr.type === 'personal') {
        // Until we allow sending zephyrs based on multiple meaningful
        // representations of a user (name, username, email, etc.), just
        // deal with usernames.
        recipient = zephyr.display_recipient;
        if ( recipient === username) { // that is, we sent the original message
            recipient = zephyr.sender;
        }
        prepare_huddle(recipient);
    }


}

function update_pointer(zephyr) {
    var new_selected = get_id(zephyr);
    if (new_selected == selected_zephyr_id)
        return;
    selected_zephyr_id = new_selected;

    $('.selected_zephyr').removeClass('selected_zephyr');
    zephyr.addClass('selected_zephyr');

    $.post("update", { pointer: selected_zephyr_id });
}

function update_pointer_by_id(zephyr_id) {
    update_pointer(get_zephyr(zephyr_id));
}

function select_zephyr(zephyr_id) {
    var next_zephyr = get_zephyr(zephyr_id);
    var main_div = $("#main_div");

    /* If the zephyr exists but is hidden, try to find the next visible one. */
    if (next_zephyr.length !== 0 && next_zephyr.is(':hidden')) {
        next_zephyr = get_next_visible(next_zephyr);
    }

    /* Fall back to the first visible zephyr. */
    if (next_zephyr.length === 0) {
        next_zephyr = $('tr:not(:hidden):first');
    }

    update_pointer(next_zephyr);

    if ((next_zephyr.offset().top < main_div.offset().top) ||
        (next_zephyr.offset().top + next_zephyr.height() >
         main_div.offset().top + main_div.height())) {
        scroll_to_selected();
    }
}


/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

function show_email(zephyr_id) {
    get_zephyr(zephyr_id).find('.zephyr_sender_email').removeClass('invisible');
}

function hide_email(zephyr_id) {
    get_zephyr(zephyr_id).find('.zephyr_sender_email').addClass('invisible');
}


function process_hotkey(code) {
    var next_zephyr;

    switch (code) {
    case 40: // down arrow
    case 38: // up arrow
        if (code === 40) {
            next_zephyr = get_next_visible(get_zephyr(selected_zephyr_id));
        } else {
            next_zephyr = get_prev_visible(get_zephyr(selected_zephyr_id));
        }
        if (next_zephyr.length !== 0) {
            select_zephyr(get_id(next_zephyr));
        }
        if ((next_zephyr.length === 0) && (code === 40)) {
            // At the last zephyr, scroll to the bottom so we have
            // lots of nice whitespace for new zephyrs coming in.
            $("#main_div").scrollTop($("#main_div").prop("scrollHeight"));
        }
        return process_hotkey;

    case 27: // Esc: hide compose pane
        hide_compose();
        return process_hotkey;

    case 82: // 'r': respond to zephyr
        respond_to_zephyr();
        return process_key_in_input;

    case 71: // 'g': start of "go to" command
        return process_goto_hotkey;
    }

    return false;
}

function process_goto_hotkey(code) {
    switch (code) {
    case 67: // 'c': narrow by recipient
        parent = get_zephyr(selected_zephyr_id);
        zephyr_class = parent.find(".zephyr_class").text();
        zephyr_huddle = parent.find(".zephyr_huddle_recipient").text();
        if (zephyr_class == '' && zephyr_huddle == '') {
            narrow_personals();
        } else if (zephyr_class == '') {
            narrow_huddle();
        }
        else {
            narrow_class();
        }
        break;

    case 73: // 'i': narrow by instance
        narrow_instance();
        break;

    case 80: // 'p': narrow to personals
        narrow_all_personals();
        break;

    case 65: // 'a': un-narrow
        show_all_messages();
        break;

    case 27: // Esc: hide compose pane
        hide_compose();
        break;
    }

    /* Always return to the initial hotkey mode, even
       with an unrecognized "go to" command. */
    return process_hotkey;
}

function process_key_in_input(code) {
    if (code === 27) {
        // User hit Escape key
        hide_compose();
        return process_hotkey;
    }
    return false;
}

/* The current handler function for keydown events.
   It should return a new handler, or 'false' to
   decline to handle the event. */
var keydown_handler = process_hotkey;

$(document).keydown(function (event) {
    var result = keydown_handler(event.keyCode);
    if (typeof result === 'function') {
        keydown_handler = result;
        event.preventDefault();
    }
});

// NB: This just binds to current elements, and won't bind to elements
// created after ready() is called.

$(function () {
    $('input, textarea, button').focus(function () {
        keydown_handler = process_key_in_input;
    });
    $('input, textarea, button').blur(function () {
        keydown_handler = process_hotkey;
    });
});

function home_view(element) {
    return true;
}

var current_view_predicate = home_view;

function apply_view(element) {
    if (current_view_predicate(element)) {
        element.show();
    } else {
        element.hide();
    }
}

function prepare_huddle(recipients) {
    // Used for both personals and huddles.
    show_compose('personal');
    $("#recipient").val(recipients);
    $("#new_personal_zephyr").focus();
    $("#new_personal_zephyr").select();
}

function do_narrow(description, filter_function) {
    // Hide the messages temporarily, so the browser doesn't waste time
    // incrementally recalculating the layout.
    $("#main_div").hide();

    // We want the zephyr on which the narrow happened to stay in the same place if possible.
    var old_top = $("#main_div").offset().top - get_zephyr(selected_zephyr_id).offset().top;
    current_view_predicate = filter_function;
    get_all_zephyr_rows().each(function () {
        apply_view($(this));
    });

    // Show the new set of messages.
    $("#main_div").show();

    select_zephyr(selected_zephyr_id);
    scroll_to_selected();

    $("#show_all_messages").removeAttr("disabled");
    $("#narrowbox").show();
    $("#currently_narrowed_to").html(description);
}

function narrow_huddle() {
    var recipients = get_zephyr(selected_zephyr_id).find(".zephyr_huddle_recipients_list").text();
    var message = "Group chats with " + recipients;
    do_narrow(message, function (element) {
        return (element.find(".zephyr_huddle_recipient").length > 0 &&
                element.find(".zephyr_huddle_recipients_list").text() === recipients);
    });
}

function narrow_all_personals() {
    // Narrow to all personals
    var message = "All huddles with you";
    do_narrow(message, function (element) {
        return (element.find(".zephyr_personal_recipient").length > 0);
    });
}

function narrow_personals() {
    // Narrow to personals with a specific user
    var target_zephyr = get_zephyr(selected_zephyr_id);
    var zephyr_obj = zephyr_dict[target_zephyr.attr('id')];
    var other_party;
    if (zephyr_obj.display_recipient === username) {
        other_party = zephyr_obj.sender;
    } else {
        other_party = zephyr_obj.display_recipient;
    }
    var message = "Huddles with " + other_party;
    do_narrow(message, function (element) {
        var other_zephyr_obj = zephyr_dict[target_zephyr.attr('id')];
        var recipient = element.find(".zephyr_personal_recipient");
        var sender = element.find(".zephyr_sender");

        return (recipient.length > 0) &&
            (((other_zephyr_obj.display_recipient === zephyr_obj.display_recipient) && (other_zephyr_obj.sender === zephyr_obj.sender)) ||
             ((other_zephyr_obj.display_recipient === zephyr_obj.sender) && (other_zephyr_obj.sender === zephyr_obj.display_recipient)));
    });
}

function narrow_class() {
    var parent = get_zephyr(selected_zephyr_id);
    var zephyr_class = parent.find(".zephyr_class").text();
    var message = "<span class='zephyr_class'>" + zephyr_class + "</span>";
    do_narrow(message, function (element) {
        return (element.find(".zephyr_class").length > 0 &&
                element.find(".zephyr_class").text() === zephyr_class);
    });
}

function narrow_instance() {
    var parent = get_zephyr(selected_zephyr_id);
    var zephyr_class = parent.find(".zephyr_class").text();
    var zephyr_instance = parent.find(".zephyr_instance").text();
    var message = "<span class='zephyr_class'>" + zephyr_class
        + "</span> | <span class='zephyr_instance'>" + zephyr_instance + "</span>";
    do_narrow(message, function (element) {
        return (element.find(".zephyr_class").length > 0 &&
                element.find(".zephyr_class").text() === zephyr_class &&
                element.find(".zephyr_instance").text() === zephyr_instance);
    });
}

function show_all_messages() {
    current_view_predicate = home_view;
    get_all_zephyr_rows().show();

    scroll_to_selected();

    $("#narrowbox").hide();
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").html("");
}

function newline2br(content) {
    return content.replace(/\n/g, '<br />');
}

function update_autocomplete() {
    class_list.sort();
    instance_list.sort();
    people_list.sort();

    $( "#class" ).autocomplete({
        source: class_list
    });
    $( "#instance" ).autocomplete({
        source: instance_list
    });
    $( "#recipient" ).autocomplete({
        source: people_list
    });
}

function add_message(index, zephyr) {
    last_received = Math.max(last_received, zephyr.id);

    if (zephyr.type === 'class') {
        zephyr.is_class = true;
        if ($.inArray(zephyr.display_recipient, class_list) === -1) {
            class_list.push(zephyr.display_recipient);
            update_autocomplete();
        }
        if ($.inArray(zephyr.instance, instance_list) === -1) {
            instance_list.push(zephyr.instance);
            update_autocomplete();
        }
    } else if (zephyr.type === "huddle") {
        zephyr.is_huddle = true;
    } else {
        zephyr.is_personal = true;

        if (zephyr.display_recipient !== username &&
                $.inArray(zephyr.display_recipient, people_list) === -1) {
            people_list.push(zephyr.display_recipient);
            update_autocomplete();
        }
        if (zephyr.sender !== username &&
                $.inArray(zephyr.sender, people_list) === -1) {
            people_list.push(zephyr.sender);
            update_autocomplete();
        }
    }
    zephyr.html_content = newline2br(zephyr.content);

    var time = new Date(zephyr.timestamp * 1000);
    var two_digits = function (x) { return ('0' + x).slice(-2); }
    zephyr.timestr = two_digits(time.getHours())
                   + ':' + two_digits(time.getMinutes());
    zephyr.full_date_str = time.toLocaleString();

    var new_tr = $('<tr />').attr('id', zephyr.id).addClass('zephyr_row');
    $('#table').append(new_tr);
    new_tr.append(ich.zephyr(zephyr));
    apply_view(new_tr);
}

$(function () {
    $(initial_zephyr_array).each(add_message);
    select_zephyr(initial_pointer);
    get_updates_longpoll();
});

function clear_compose_box() {
    $("#zephyr_compose").find('input[type=text], textarea').val('');
}

var longpoll_failures = 0;
function get_updates_longpoll() {
    console.log(new Date() + ': longpoll started');
    $.ajax({
        type:     'POST',
        url:      'get_updates_longpoll',
        data:     { last_received: last_received },
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (data) {
            console.log(new Date() + ': longpoll success');
            longpoll_failures = 0;
            $('#connection-error').hide();

            if (data && data.zephyrs) {
                $.each(data.zephyrs, add_message);
                for (i in data.zephyrs) {
                    console.log(data.zephyrs[i]);
                    console.log(data.zephyrs[i].id);
                    zephyr_dict[data.zephyrs[i].id] = data.zephyrs[i];
                }
            }
            setTimeout(get_updates_longpoll, 0);
        },
        error: function (xhr, error_type, exn) {
            if (error_type === 'timeout') {
                // Retry indefinitely on timeout.
                console.log(new Date() + ': longpoll timed out');
                longpoll_failures = 0;
                $('#connection-error').hide();
            } else {
                console.log(new Date() + ': longpoll failed with ' + error_type +
                            ' (' + longpoll_failures + ' failures)');
                longpoll_failures += 1;
            }

            if (longpoll_failures >= 5) {
                $('#connection-error').show();
            } else {
                $('#connection-error').hide();
            }

            var retry_sec = Math.min(90, Math.exp(longpoll_failures/2));
            console.log(new Date() + ': longpoll retrying in ' + retry_sec + ' seconds');
            setTimeout(get_updates_longpoll, retry_sec*1000);
        }
    });
}

$(function () {
    update_autocomplete();
    $('.button-slide').click(show_compose);
});
