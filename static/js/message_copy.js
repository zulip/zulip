exports.copy_selected_messages = function (group) {
    selected_messages = $(".copy_selected_message");
    var messages = [];

    selected_messages.each( function() {
        var row = $(this);
        if (group == rows.get_closest_group(row).attr("id")) {
            messages.push(rows.id(row));
        }
    });

    if (Array.isArray(messages) && messages.length){
        $("#messages_markdown_" + group).show();
    } else {
        return;
    }

    return channel.get({
         url: '/json/messages/markdown',
         idempotent: true,
         data: {
             messages: JSON.stringify(messages),
         },
         success: function (data) {
            $('#copy_message_markdown_' + group).val(data.raw_content);
            const clipboard = new ClipboardJS('#btn_copy_message_markdown_' + group);
            clipboard.on('success', function() {
                show_copied_alert(group);
                clean_copied_messages(group);
            });
            clipboard.on('error', function() {
                clean_copied_messages(group);
            });
        },
    });
};

show_copied_alert = function (group) {
    const alert = $(".alert-grp").filter( function () {
        return $(this).parent(".copy_selected_messages").attr('group') === group;
    })
    alert.text(i18n.t("Copied!"));
    alert.css("display", "block");
    alert.delay(1000).fadeOut(300);
};

clean_copied_messages = function (group) {
    $("#messages_markdown_" + group).hide();
    $('#copy_message_markdown_' + group).val("");
    $(".copy_selected_message").removeClass("copy_selected_message");
};


exports.select_message = function(message_box) {
    const row = $(message_box).closest(".message_row")
    if (row.hasClass("copy_selected_message")) {
        row.removeClass("copy_selected_message");
    } else {
        row.addClass("copy_selected_message");
    }
}

window.message_copy = exports;