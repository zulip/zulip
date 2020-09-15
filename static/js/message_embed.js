"use strict";

exports.remove_preview = function (target) {
    const message_id = rows.id($(target).parents(".message_row"));
    const embed = $(target).parent();
    const url = embed.find("a").attr("href");
    channel.post({
        url: "/json/messages/" + message_id + "/remove_preview",
        data: {message_id, url},
        success() {
            embed.remove();
        },
    });
};

exports.add_preview_remove_button = function (message_row) {
    message_row
        .find(".message_content")
        .find(".message_embed")
        .each(function () {
            const button = $("<button>")
                .attr("type", "button")
                .attr("class", "close message_embed_remove")
                .attr("title", "Hide preview")
                .text("×");
            $(this).prepend(button);
            button.hide();
        });
};

exports.maybe_show_preview_remove_button = function (message_row) {
    // Display message embed close buttons if message was sent by current user, and message edit
    // time has not expired
    const message = current_msg_list.get(rows.id(message_row));
    // Keep this value the same as the value in `message_edit.js`. See `edit_message` function in
    // `message_edit.js` for more info.
    const seconds_left_buffer = 5;
    const editability = message_edit.get_editability(message, seconds_left_buffer);
    if (editability === message_edit.editability_types.FULL) {
        message_row.find("button.message_embed_remove").show();
    }
};

window.message_embed = exports;
