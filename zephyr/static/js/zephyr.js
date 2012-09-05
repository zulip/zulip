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

$(function() {
    var status_classes = 'alert-error alert-success alert-info';
    var send_status = $('#send-status');
    var buttons = $('#class-message, #personal-message').find('input[type="submit"]');

    var options = {
        beforeSubmit: function (form, _options) {
            send_status.removeClass(status_classes)
                       .addClass('alert-info')
                       .text('Sending')
                       .stop(true).fadeTo(0,1);
            buttons.attr('disabled', 'disabled');
            buttons.blur()
        },
        success: function (resp, statusText, xhr, form) {
            form.find('textarea').val('');
            send_status.removeClass(status_classes)
                       .addClass('alert-success')
                       .text('Sent message')
                       .stop(true).fadeTo(0,1).delay(1000).fadeOut(1000);
            buttons.removeAttr('disabled');
        },
        error: function() {
            send_status.removeClass(status_classes)
                       .addClass('alert-error')
                       .text('Error sending message ')
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

selected_tag = '<p id="selected">&#x25b6;</p>'

var allow_hotkeys = true;

function select_zephyr(next_zephyr) {
    p = $("#selected");
    td = $(p).closest("td");
    if (next_zephyr.length != 0) { // We are not at the bottom or top of the zephyrs.
        td.empty(); // Clear the previous arrow.
        next_zephyr.children("td:first").html(selected_tag);
        $.post("update", {pointer: next_zephyr.attr("id")});

        if (($(next_zephyr).offset().top < $("#main_div").offset().top) ||
            ($(next_zephyr).offset().top + $(next_zephyr).height() > $("#main_div").offset().top + $("#main_div").height())) {
            scroll_to_selected();
        }
    }
}

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
        select_zephyr($(this).parent().parent());
    });
});

var goto_pressed = false;


$(document).keydown(function(event) {
    if (allow_hotkeys) {

        if (event.keyCode == 38 || event.keyCode == 40) { // down or up arrow

            p = $("#selected");
            tr = $(p).closest("tr");
            if (event.keyCode == 40) { // down arrow
                // There are probably more verbose but more efficient ways to do this.
                next_zephyr = tr.nextAll(":not(:hidden):first");
            } else { // up arrow
                next_zephyr = tr.prevAll(":not(:hidden):first");
            }
            select_zephyr(next_zephyr);
            event.preventDefault();
        } else if (event.keyCode == 82) { // 'r' keypress, for responding to a zephyr
            var parent = $("#selected").parents("tr");
            var zephyr_class = parent.find("span.zephyr_class").text();
            var instance = parent.find("span.zephyr_instance").text();
            if (zephyr_class != '') {
                $('#zephyr-type-tabs a[href="#class-message"]').tab('show');
                $("#class").val(zephyr_class);
                $("#instance").val(instance);
                $("#new_zephyr").focus();
                $("#new_zephyr").select();
            } else { // must be a personal
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
            var parent = $("#selected").parents("tr");
            var zephyr_class = parent.find("span.zephyr_class").text();
            narrow_class(zephyr_class, parent.attr("id"));
            event.preventDefault()
        } else if (goto_pressed && event.keyCode == 73) { // 'i' keypress, for narrow-by-instance
            var parent = $("#selected").parents("tr");
            var zephyr_class = parent.find("span.zephyr_class").text();
            var zephyr_instance = parent.find("span.zephyr_instance").text();
            narrow_instance(zephyr_class, zephyr_instance, parent.attr("id"));
            event.preventDefault()
        } else if (goto_pressed && event.keyCode == 80) { // 'p' keypress, for narrow-to-personals
            narrow_all_personals($("#selected").parents("tr").attr("id"));
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
    $('#main_div').scrollTop(0);
    $('#main_div').scrollTop($("#selected").offset().top - $('#main_div').height()/1.5);

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

function do_narrow(target_zephyr, description, filter_function) {
    // We want the zephyr on which the narrow happened to stay in the same place if possible.
    var old_top = $("#main_div").offset().top - $("#" + target_zephyr).offset().top;
    current_view_predicate = filter_function;
    $("tr").each(function() {
        current_view($(this))
    });

    $("#selected").closest("td").empty();
    $("#" + target_zephyr).children("td:first").html(selected_tag);
    $.post("update", {pointer: target_zephyr});

    scroll_to_selected();

    $("#unhide").removeAttr("disabled");
    $("#narrow_indicator").html(description);
}

function narrow_huddle(target_zephyr) {
    // This probably should be specific to a particular group chat, not all of them
    var message = "Showing group chats";
    do_narrow(target_zephyr, message,
              function(element) {
                  return (element.find("span.zephyr_huddle_recipient").length > 0);
              }
             );
}

function narrow_all_personals(target_zephyr) {
    // Narrow to all personals
    var message = "Showing personals";
    do_narrow(target_zephyr, message,
              function(element) {
                  return (element.find("span.zephyr_personal_recipient").length > 0);
              }
              );
}

function narrow_personals(target_zephyr) {
    // Narrow to personals with a specific user
    var message = "Showing personals";
    var target_recipient = $("#" + target_zephyr).find("span.zephyr_personal_recipient").text();
    var target_sender = $("#" + target_zephyr).find("span.zephyr_sender").text();
    do_narrow(target_zephyr, message,
              function(element) {
                  var recipient = element.find("span.zephyr_personal_recipient");
                  var sender = element.find("span.zephyr_sender");

                  return ((recipient.length > 0) &&
                          ((recipient.text() == target_recipient) && (sender.text() == target_sender)) ||
                          ((recipient.text() == target_sender) && (sender.text() == target_recipient)));
              }
              );
}

function narrow_class(class_name, target_zephyr) {
    var message = "Showing <span class='label zephyr_class'>" + class_name + "</span>";
    do_narrow(target_zephyr, message,
              function(element) {
                  return (element.find("span.zephyr_class").length > 0 &&
                          element.find("span.zephyr_class").text() == class_name);
              }
             );
}

function narrow_instance(class_name, instance, target_zephyr) {
    var message = "Showing <span class='label zephyr_class'>" + class_name
        + "</span> <span class='label zephyr_instance'>" + instance + "</span>";
    do_narrow(target_zephyr, message,
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
        select_zephyr($("#" + initial_pointer));
        get_updates_longpoll();
    });
});

var longpoll_failures = 0;

function get_updates_longpoll(data) {
    if (data && data.zephyrs) {
        $.each(data.zephyrs, add_message);
    }
    var last_received = 0;
    if ($("tr:last").attr("id")) {
        last_received = $("tr:last").attr("id");
    }
    $.ajax({
        type:     'POST',
        url:      'get_updates_longpoll',
        data:     { last_received: last_received },
        dataType: 'json',
        success: function (data) {
            longpoll_failures = 0;
            get_updates_longpoll(data);
        },
        error: function () {
            longpoll_failures += 1;
            if (longpoll_failures >= 6) {
                $('#connection-error').show();
                resize_main_div();
            } else {
                setTimeout(get_updates_longpoll, 5*1000);
            }
        }
    });
}

$(function() {
    update_autocomplete();
});
