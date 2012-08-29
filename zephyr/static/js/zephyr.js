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

selected_tag = '<p id="selected">&#x25b6;</p>'

function textarea_in_focus() {
    return $("#class").is(":focus") || $("#instance").is(":focus") || $("#new_zephyr").is(":focus") || $("#new_personal_zephyr").is("focus");
}

$(document).keydown(function(event) {
    if (event.keyCode == 38 || event.keyCode == 40) { // down or up arrow
	// Remove focus from zephyr creation.
	$("#new_zephyr").blur();
	$("#new_personal_zephyr").blur();

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
    } else if ((event.keyCode == 82) && !textarea_in_focus()) { // 'r' keypress, for responding to a zephyr
        var parent = $("#selected").parents("tr");
        var zephyr_class = parent.find("span.zephyr_class").text();
	var instance = parent.find("span.zephyr_instance").text();
        $("#class").val(zephyr_class);
        $("#instance").val(instance);
        $("#new_zephyr").focus();
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

$(function() {
  setInterval(get_updates, 1000);
});

function newline2br(content) {
    return content.replace(/\n/g, '<br />');
}

function add_message(index, zephyr) {
    var new_str = "<tr id=" + zephyr.id + ">" +
	"<td class='pointer'><p></p></td>" +
	"<td class='zephyr'><p>";
    if (zephyr.type == "class") {
        new_str += "<span onclick=\"narrow('" + zephyr.display_recipient + "','" + zephyr.id
                   + "')\" class='label zephyr_class'>" + zephyr.display_recipient + "</span> "
                +  "<span onclick=\"narrow_instance('" + zephyr.display_recipient + "','" +
                   zephyr.instance + "','" + zephyr.id + "')\" class='label zephyr_instance'>" +
                   zephyr.instance + "</span> ";
    } else {
        new_str += "<span onclick=\"narrow_personals('" + zephyr.id + "')\" class='label zephyr_personal_recipient'>" +
                   zephyr.display_recipient + "</span>"
                   + " &larr; ";
    }
    new_str += "<span onclick=\"prepare_personal('" + zephyr.sender + "')\" class='label zephyr_sender'>"
        + zephyr.sender + "</span><br />"
	+ newline2br(zephyr.content) +
	"</p></td>" +
	"</tr>";
    $("#table tr:last").after(new_str);
}

function get_updates() {
    var last_received = $("tr:last").attr("id");
    $.post("get_updates", {last_received: last_received},
           function(data) {
               $.each(data, add_message);
    }, "json");
}
