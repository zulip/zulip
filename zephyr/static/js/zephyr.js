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
                       .html('Error sending message ')
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

// NB: This just binds to current elements, and won't bind to elements
// created after ready() is called.

$(document).ready(function() {
    $('input, textarea, button').focus(function() {
          allow_hotkeys = false;
    });

    $('input, textarea, button').blur(function() {
          allow_hotkeys = true;
    });
});

var goto_pressed = false;

$(document).keydown(function(event) {
    if (allow_hotkeys) {

        if (event.keyCode == 38 || event.keyCode == 40) { // down or up arrow
            p = $("#selected");
            tr = $(p).closest("tr");
            td = $(p).closest("td");

            if (event.keyCode == 40) { // down arrow
                // There are probably more verbose but more efficient ways to do this.
                next_zephyr = tr.nextAll(":not(:hidden):first");
            } else { // up arrow
                next_zephyr = tr.prevAll(":not(:hidden):first");
            }
            if (next_zephyr.length != 0) { // We are not at the bottom or top of the zephyrs.
                next_zephyr.children("td:first").html(selected_tag);
                td.empty(); // Clear the previous arrow.
                $.post("update", {pointer: next_zephyr.attr("id")});

                if ($(next_zephyr).offset().top < $("#main_div").offset().top) {
                    $("#main_div").scrollTop($("#main_div").scrollTop() - 75);
                }

                if ($(next_zephyr).offset().top + $(next_zephyr).height() > $("#main_div").offset().top + $("#main_div").height()) {
                    $("#main_div").scrollTop($("#main_div").scrollTop() + 75);
                }
            }
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
            } else { // No instance, must be a personal
                prepare_personal(parent.find("span.zephyr_sender").text());
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
            narrow(zephyr_class, parent.attr("id"));
            event.preventDefault()
        } else if (goto_pressed && event.keyCode == 73) { // 'i' keypress, for narrow-by-instance
            var parent = $("#selected").parents("tr");
            var zephyr_class = parent.find("span.zephyr_class").text();
            var zephyr_instance = parent.find("span.zephyr_instance").text();
            narrow_instance(zephyr_class, zephyr_instance, parent.attr("id"));
            event.preventDefault()
        } else if (goto_pressed && event.keyCode == 80) { // 'p' keypress, for narrow-to-personals
            narrow_personals($("#selected").parents("tr").attr("id"));
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

function scroll_to_zephyr(target_zephyr, old_offset) {
    // target_zephyr is an id.
    // old_offset is how far from the top of the scroll area the
    // zephyr was before any narrowing or unnarrowing happened.
    var height_above_zephyr = 0;
    $("#table tr:lt(" + $("#" + target_zephyr).index() + ")").each(function() {
        if (!$(this).is(":hidden")) {
            height_above_zephyr += $(this).height();
        }
    });
    $("#main_div").scrollTop(height_above_zephyr + old_offset);
}

function hide_personals() {
    $("span.zephyr_personal_recipient").each(
        function() {
            $(this).parents("tr").hide();
        }
    );
}

function narrow_personals(target_zephyr) {
    var old_top = $("#main_div").offset().top - $("#" + target_zephyr).offset().top;

    $("span.zephyr_personal_recipient").each(
        function() {
            $(this).parents("tr").show();
        }
    );
    $("span.zephyr_class").each(
        function() {
            $(this).parents("tr").hide();
        }
    );

    $("#selected").closest("td").empty();
    $("#" + target_zephyr).children("td:first").html(selected_tag);
    $.post("update", {pointer: target_zephyr});
    scroll_to_zephyr(target_zephyr, old_top);

    $("#unhide").removeAttr("disabled");
    $("#narrow_indicator").html("Showing personals");
}

function narrow(class_name, target_zephyr) {
    // We want the zephyr on which the narrow happened to stay in the same place if possible.
    var old_top = $("#main_div").offset().top - $("#" + target_zephyr).offset().top;
    $("span.zephyr_class").each(
        function() {
            if ($(this).text() != class_name) {
                $(this).parents("tr").hide();
            } else {
                // If you've narrowed on an instance and then click on the class, that should unhide the other instances on that class.
                $(this).parents("tr").show();
	    }
        }
    );
    hide_personals();
    $("#selected").closest("td").empty();
    $("#" + target_zephyr).children("td:first").html(selected_tag);
    $.post("update", {pointer: target_zephyr});

    // Try to keep the zephyr in the same place on the screen after narrowing.
    scroll_to_zephyr(target_zephyr, old_top);

    $("#unhide").removeAttr("disabled");
    $("#narrow_indicator").html("Showing <span class='label zephyr_class'>" + class_name + "</span>");
}

function narrow_instance(class_name, instance, target_zephyr) {
    var old_top = $("#main_div").offset().top - $("#" + target_zephyr).offset().top;
    $("tr").each(
        function() {
            if (($(this).find("span.zephyr_class").text() != class_name) ||
		($(this).find("span.zephyr_instance").text() != instance)) {
                $(this).hide();
	    }
        }
    );
    hide_personals();
    $("#selected").closest("td").empty();
    $("#" + target_zephyr).children("td:first").html(selected_tag);
    $.post("update", {pointer: target_zephyr});

    // Try to keep the zephyr in the same place on the screen after narrowing.
    scroll_to_zephyr(target_zephyr, old_top);

    $("#unhide").removeAttr("disabled");
    $("#narrow_indicator").html("Showing <span class='label zephyr_class'>" + class_name
      + "</span> <span class='label zephyr_instance'>" + instance + "</span>");
}

function prepare_personal(username) {
    $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
    $("#recipient").val(username);
    $("#new_personal_zephyr").focus();
}

function unhide() {
    $("tr").show();

    p = $("#selected");
    tr = $(p).closest("tr");
    scroll_to_zephyr(tr.attr("id"), 0);

    $("#unhide").attr("disabled", "disabled");
    $("#narrow_indicator").html("");
}

function newline2br(content) {
    return content.replace(/\n/g, '<br />');
}

function add_message(index, zephyr) {
    var zephyr_para = $('<p />');
    var new_label = function (text, classes, on_click) {
        zephyr_para.append($('<span />')
            .text(text)
            .addClass('label zephyr_label_clickable ' + classes)
            .click(on_click));
        zephyr_para.append('&nbsp;');
    };

    if (zephyr.type == 'class') {
        new_label(zephyr.display_recipient, 'zephyr_class',
            function (e) { narrow(zephyr.display_recipient, zephyr.id); });
        new_label(zephyr.instance, 'zephyr_instance',
            function (e) { narrow_instance(zephyr.display_recipient,
                                           zephyr.instance, zephyr.id); });
    } else {
        new_label(zephyr.display_recipient, 'zephyr_personal_recipient',
            function (e) { narrow_personals(zephyr.id); });
        zephyr_para.append('&larr;&nbsp;');
    }

    new_label(zephyr.sender, 'zephyr_sender',
             function (e) { prepare_personal(zephyr.sender); });

    zephyr_para.append('<br />' + newline2br(zephyr.content));

    $('#table tr:last').after($('<tr />')
        .attr('id', zephyr.id)
        .append('<td class="pointer"><p></p></td>')
        .append($('<td />').append(zephyr_para)));
}

$(function() {
  $(initial_zephyr_json).each(add_message);
});

function get_updates_longpoll(data) {
    if (data && data.zephyrs) {
	$.each(data.zephyrs, add_message);
    }
    var last_received = $("tr:last").attr("id");
    $.post("get_updates_longpoll",
	   {last_received: last_received},
	    function(data) {
		get_updates_longpoll(data);
	    }, "json");
}

$(document).ready(function() {
    get_updates_longpoll()
});

