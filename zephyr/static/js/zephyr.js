function resize_main_div() {
    // Resize main_div to exactly take up remaining vertical space.
    var div = $('#main_div');
    div.height(Math.max(200, div.height() + $(window).height() - $('body').height()));
}
$(function () {
    resize_main_div();
    $(window).resize(resize_main_div);
    $('#zephyr-type-tabs a').on('shown', function (e) { resize_main_div(); });
});

$(function() {
    $('#zephyr-type-tabs a[href="#class-message"]').on('shown', function (e) {
        $('#class-message input:not(:hidden):first').focus().select();
    });
    $('#zephyr-type-tabs a[href="#personal-message"]').on('shown', function (e) {
        $('#personal-message input:not(:hidden):first').focus().select();
    });
});

$.ajaxSetup({
     beforeSend: function(xhr, settings) {
         function getCookie(name) {
             var cookieValue = null;
             if (document.cookie && document.cookie != '') {
                 var cookies = document.cookie.split(';');
                 for (var i = 0; i < cookies.length; i++) {
                     var cookie = jQuery.trim(cookies[i]);
                     // Does this cookie string begin with the name we want?
                 if (cookie.substring(0, name.length + 1) == (name + '=')) {
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

$(function() {
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
            buttons.attr('disabled', 'disabled');
            buttons.blur()

            if ($("#class-message:visible")[0] == undefined) {// we're not dealing with classes
                return true;
            }
            var okay = true;
            $.ajaxSetup({async:false}); // so we get blocking gets
            $.get("subscriptions/exists/" + $("#class").val(), function(data) {
                if (data == "False") {
                    // The class doesn't exist
                    okay = false;
                    send_status.removeClass(status_classes)
                    send_status.toggle();
                    $('#class-dne-name').text($("#class").val());
                    $('#class-dne').show();
                    $('#create-it').focus()
                                   .click(function() {
                        sub($("#class").val());
                        $("#class-message form").ajaxSubmit();
                        $('#class-dne').stop(true).fadeOut(500);
                                   });
                    buttons.removeAttr('disabled');
                }
            });
            $.ajaxSetup({async:true});
            if (okay && class_list.indexOf($("#class").val()) == -1) {
                // You're not subbed to the class
                okay = false;
                send_status.removeClass(status_classes);
                send_status.toggle();
                $('#class-nosub-name').text($("#class").val());
                $('#class-nosub').show();
                $('#sub-it').focus()
                            .click(function() {
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
        },
        error: function(xhr) {
            var response = "Error sending message";
            if (xhr.status.toString().charAt(0) == "4") {
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

var tag_for_selected = '<p id="selected">&#x25b6;</p>';
var selected_zephyr_id = 0;  /* to be filled in on document.ready */

function select_zephyr(zephyr_id) {
    var next_zephyr = $('#' + zephyr_id);

    /* If the zephyr exists but is hidden, try to find the next visible one. */
    if (next_zephyr.length != 0 && next_zephyr.is(':hidden')) {
        next_zephyr = next_zephyr.nextAll(':not(:hidden):first');
    }

    /* Fall back to the first visible zephyr. */
    if (next_zephyr.length == 0) {
        next_zephyr = $('tr:not(:hidden):first');
    }

    selected_zephyr_id = next_zephyr.attr('id');

    // Clear the previous arrow.
    $("#selected").closest("td").empty();

    next_zephyr.children("td:first").html(tag_for_selected);
    $.post("update", { pointer: selected_zephyr_id });

    var main_div = $("#main_div");
    if ((next_zephyr.offset().top < main_div.offset().top) ||
        (next_zephyr.offset().top + next_zephyr.height() >
         main_div.offset().top + main_div.height())) {
        scroll_to_selected();
    }
}

function get_selected_zephyr_row() {
    return $('#' + selected_zephyr_id);
}

var allow_hotkeys = true;
var goto_pressed = false;

// NB: This just binds to current elements, and won't bind to elements
// created after ready() is called.

$(document).ready(function() {
    $('input, textarea, button').focus(function() {
          allow_hotkeys = false;
    });

    $('input, textarea, button').blur(function() {
          allow_hotkeys = true;
    });
    $("body").delegate("p", "click", function(){
        select_zephyr($(this).parent().parent().attr('id'));
    });
});

$(document).keydown(function(event) {
    if (allow_hotkeys) {

        if (event.keyCode == 38 || event.keyCode == 40) { // down or up arrow

            var tr = get_selected_zephyr_row();
            if (event.keyCode == 40) { // down arrow
                // There are probably more verbose but more efficient ways to do this.
                next_zephyr = tr.nextAll(":not(:hidden):first");
            } else { // up arrow
                next_zephyr = tr.prevAll(":not(:hidden):first");
            }
            if (next_zephyr.length != 0) {
                select_zephyr(next_zephyr.attr('id'));
            }
            event.preventDefault();
        } else if (event.keyCode == 82) { // 'r' keypress, for responding to a zephyr
            var parent = get_selected_zephyr_row();
            var zephyr_class = parent.find("span.zephyr_class").text();
            var zephyr_huddle = parent.find("span.zephyr_huddle_recipient").text();
            var zephyr_personal = parent.find("span.zephyr_personal_recipient").text();
            var instance = parent.find("span.zephyr_instance").text();
            if (zephyr_class != '') {
                $('#zephyr-type-tabs a[href="#class-message"]').tab('show');
                $("#class").val(zephyr_class);
                $("#instance").val(instance);
                $("#new_zephyr").focus();
                $("#new_zephyr").select();
            } else if (zephyr_huddle != '') {
                var recipients = parent.find("span.zephyr_huddle_recipients_list").text();
                $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
                $("#recipient").val(recipients);
                $("#new_personal_zephyr").focus();
                $("#new_personal_zephyr").select();
            } else if (zephyr_personal != '') {
                var recipient = parent.find("span.zephyr_sender").text();
                if (recipient == username) { // that is, we sent the original message
                    recipient = parent.find("span.zephyr_personal_recipient").text();
                }
                $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
                $("#recipient").val(recipient);
                $("#new_personal_zephyr").focus();
                $("#new_personal_zephyr").select();
            }
            event.preventDefault();
        } else if (event.keyCode == 71) { // 'g' keypress, set trigger for "go to"
            goto_pressed = true;
            event.preventDefault();
        } else if (goto_pressed && event.keyCode == 67) { // 'c' keypress, for narrow-by-recipient
            var parent = get_selected_zephyr_row();
            var zephyr_class = parent.find("span.zephyr_class").text();
            narrow_class(zephyr_class);
            event.preventDefault()
        } else if (goto_pressed && event.keyCode == 73) { // 'i' keypress, for narrow-by-instance
            var parent = get_selected_zephyr_row();
            var zephyr_class = parent.find("span.zephyr_class").text();
            var zephyr_instance = parent.find("span.zephyr_instance").text();
            narrow_instance(zephyr_class, zephyr_instance);
            event.preventDefault()
        } else if (goto_pressed && event.keyCode == 80) { // 'p' keypress, for narrow-to-personals
            narrow_all_personals();
            event.preventDefault();
        } else if (goto_pressed && event.keyCode == 65) { // 'a' keypress, for unnarrow
            unhide();
            event.preventDefault();
        }

        if (event.keyCode != 71) { // not 'g'
            goto_pressed = false;
        }

    } else if (event.keyCode == 27) { // Esc pressed
        $('input, textarea, button').blur();
        event.preventDefault();
    }
});

function scroll_to_selected() {
    var main_div = $('#main_div');
    main_div.scrollTop(0);
    main_div.scrollTop(get_selected_zephyr_row().offset().top - main_div.height()/1.5);
}

function home_view(element) {
    return true;
}

var current_view_predicate = home_view;

function current_view(element) {
    if (current_view_predicate(element)) {
        element.show();
    } else {
        element.hide();
    }
}

function do_narrow(description, filter_function) {
    // We want the zephyr on which the narrow happened to stay in the same place if possible.
    var old_top = $("#main_div").offset().top - get_selected_zephyr_row().offset().top;
    current_view_predicate = filter_function;
    $("tr").each(function() {
        current_view($(this))
    });

    select_zephyr(selected_zephyr_id);
    scroll_to_selected();

    $("#unhide").removeAttr("disabled");
    $("#narrow_indicator").html(description);
}

function narrow_huddle() {
    var recipients = get_selected_zephyr_row().find("span.zephyr_huddle_recipients_list").text();
    var message = "Showing group chats with " + recipients;
    do_narrow(message,
              function(element) {
                  return (element.find("span.zephyr_huddle_recipient").length > 0 &&
                          element.find("span.zephyr_huddle_recipients_list").text() == recipients);
              }
             );
}

function narrow_all_personals() {
    // Narrow to all personals
    var message = "Showing all personals";
    do_narrow(message,
              function(element) {
                  return (element.find("span.zephyr_personal_recipient").length > 0);
              }
              );
}

function narrow_personals() {
    // Narrow to personals with a specific user
    var target_zephyr = get_selected_zephyr_row();
    var target_recipient = target_zephyr.find("span.zephyr_personal_recipient").text();
    var target_sender = target_zephyr.find("span.zephyr_sender").text();
    var other_party;
    if (target_recipient == username) {
        other_party = target_sender;
    } else {
        other_party = target_recipient;
    }
    var message = "Showing personals with " + other_party;
    do_narrow(message,
              function(element) {
                  var recipient = element.find("span.zephyr_personal_recipient");
                  var sender = element.find("span.zephyr_sender");

                  return ((recipient.length > 0) &&
                          ((recipient.text() == target_recipient) && (sender.text() == target_sender)) ||
                          ((recipient.text() == target_sender) && (sender.text() == target_recipient)));
              }
              );
}

function narrow_class(class_name) {
    var message = "Showing <span class='label zephyr_class'>" + class_name + "</span>";
    do_narrow(message,
              function(element) {
                  return (element.find("span.zephyr_class").length > 0 &&
                          element.find("span.zephyr_class").text() == class_name);
              }
             );
}

function narrow_instance(class_name, instance) {
    var message = "Showing <span class='label zephyr_class'>" + class_name
        + "</span> <span class='label zephyr_instance'>" + instance + "</span>";
    do_narrow(message,
              function(element) {
                  return (element.find("span.zephyr_class").length > 0 &&
                          element.find("span.zephyr_class").text() == class_name &&
                          element.find("span.zephyr_instance").text() == instance);
              }
             );
}

function unhide() {
    current_view_predicate = home_view;
    $("tr").show();

    scroll_to_selected();

    $("#unhide").attr("disabled", "disabled");
    $("#narrow_indicator").html("");
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
    if (zephyr.type == 'class') {
        zephyr.is_class = true;
        if ($.inArray(zephyr.display_recipient, class_list) == -1) {
            class_list.push(zephyr.display_recipient);
            update_autocomplete();
        }
        if ($.inArray(zephyr.instance, instance_list) == -1) {
            instance_list.push(zephyr.instance);
            update_autocomplete();
        }
    } else if (zephyr.type == "huddle") {
        zephyr.is_huddle = true;
    } else {
        zephyr.is_personal = true;

        if (zephyr.display_recipient != username &&
                $.inArray(zephyr.display_recipient, people_list) == -1) {
            people_list.push(zephyr.display_recipient);
            update_autocomplete();
        }
        if (zephyr.sender != username &&
                $.inArray(zephyr.sender, people_list) == -1) {
            people_list.push(zephyr.sender);
            update_autocomplete();
        }
    }
    zephyr.html_content = newline2br(zephyr.content);

    var new_tr = $('<tr />').attr('id', zephyr.id);
    $('#table').append(new_tr);
    new_tr.append(ich.zephyr(zephyr));
    current_view(new_tr);
}

$(function () {
    /* We can't easily embed this client-side template in index.html,
       because its syntax conflicts with Django's. */
    $.get('/static/templates/zephyr.html', function (template) {
        ich.addTemplate('zephyr', template);
        $(initial_zephyr_json).each(add_message);
        select_zephyr(initial_pointer);
        get_updates_longpoll();
    });
});

var longpoll_failures = 0;
function get_updates_longpoll() {
    var last_received = 0;
    if ($("tr:last").attr("id")) {
        last_received = $("tr:last").attr("id");
    }
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
            }
            setTimeout(get_updates_longpoll, 0);
        },
        error: function (xhr, error_type, exn) {
            if (error_type == 'timeout') {
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
            resize_main_div();

            var retry_sec = Math.min(90, Math.exp(longpoll_failures/2));
            console.log(new Date() + ': longpoll retrying in ' + retry_sec + ' seconds');
            setTimeout(get_updates_longpoll, retry_sec*1000);
        }
    });
}

$(function() {
    update_autocomplete();
});
