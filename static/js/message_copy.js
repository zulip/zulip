exports.messages = [];

exports.copy_selected_messages = function (message_id) {
    const selected_messages = $(".copy_selected_message");
    for (let i = 0; i < selected_messages.length; i = i + 1) {
        exports.push_message(selected_messages.eq(i));
    }
    return channel.get({
        url: '/json/messages',
        idempotent: true,
        data: {
            anchor: "no_anchor",
            num_after: 0,
            num_before: 0,
            apply_markdown: false,
            message_id_list: JSON.stringify(exports.messages),
        },
        success: function (data) {
            const markdown = exports.concat_markdown(data.messages);
            $('#copy_message_markdown_' + message_id).val(markdown);
            const clipboard = new ClipboardJS('#btn_copy_message_markdown_' + message_id);
            clipboard.on('success', exports.clipboard_success_handler);
            clipboard.on('error', exports.clipboard_error_handler);
        },
    });
};
exports.concat_markdown = function (messages) {
    let markdown_code = "";
    messages.forEach((msg) => {
        const time = new XDate(msg.timestamp * 1000);
        const tz_offset = -time.getTimezoneOffset() / 60;
        const date = time.toLocaleDateString() + " " + time.toLocaleTimeString() +
        ' (UTC' + (tz_offset < 0 ? '' : '+') + tz_offset + ')';
        markdown_code = markdown_code.concat(date)
            .concat(" @_**" + msg.sender_full_name + "**: \n\n")
            .concat(msg.content + "\n\n");
    });
    return markdown_code;
};

exports.clipboard_success_handler = function (e) {
    const message_id = $(e.trigger).attr('data-message');
    exports.show_copied_alert(message_id);
    exports.clean_copied_messages(message_id);
};

exports.clipboard_error_handler = function (e) {
    const message_id = $(e.trigger).attr('data-message');
    exports.clean_copied_messages(message_id);
};

exports.push_message = function (message_row) {
    const row = $(message_row);
    exports.messages.push(rows.id(row));
};

exports.show_copied_alert = function (message_id) {
    const row = $(".selected_message[zid='" + message_id + "']");
    row.find(".alert-msg")
        .text(i18n.t("Copied!"))
        .css("display", "block")
        .delay(1000)
        .fadeOut(300);
};

exports.clean_copied_messages = function (message_id) {
    popovers.hide_actions_popover();
    $(".copy_selected_message").removeClass("copy_selected_message");
    $("#messages_markdown_" + message_id).hide();
    $('#copy_message_markdown_' + message_id).val("");
    exports.messages = [];
};


exports.select_message = function (message_box) {
    const row = $(message_box).closest(".message_row");
    if (row.hasClass("copy_selected_message")) {
        row.removeClass("copy_selected_message");
    } else {
        row.addClass("copy_selected_message");
    }
};

exports.select_until_message = function (first_row, final_row) {
    if (rows.id(first_row) > rows.id(final_row)) {
        return;
    }
    let current = first_row;
    while (current.length > 0) {
        current.addClass("copy_selected_message");
        current = rows.next_visible(current);
        if (rows.id(current) === rows.id(final_row)) {
            current.addClass("copy_selected_message");
            break;
        }
    }
};

window.message_copy = exports;
