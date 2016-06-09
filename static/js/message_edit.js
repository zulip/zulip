var message_edit = (function () {
var exports = {};
var currently_editing_messages = {};


// Returns true if the edit task should end.
exports.save = function (row, from_topic_edited_only) {
    var msg_list = current_msg_list;
    var message_id;

    if (row.hasClass('recipient_row')) {
        message_id = rows.id_for_recipient_row(row);
    } else {
        message_id = rows.id(row);
    }
    var message = current_msg_list.get(message_id);
    var changed = false;

    var new_content = row.find(".message_edit_content").val();
    var topic_changed = false;
    var new_topic;
    if (message.type === "stream") {
        new_topic = row.find(".message_edit_topic").val();
        topic_changed = (new_topic !== message.subject && new_topic.trim() !== "");
    }

    // Editing a not-yet-acked message (because the original send attempt failed)
    // just results in the in-memory message being changed
    if (message.local_id !== undefined) {
        // No changes
        if (new_content === message.raw_content && !topic_changed) {
            return true;
        }
        echo.edit_locally(message, new_content, topic_changed ? new_topic : undefined);
        return true;
    }

    var request = {message_id: message.id};
    if (topic_changed) {
        request.subject = new_topic;
        if (feature_flags.propagate_topic_edits) {
            var selected_topic_propagation = row.find("select.message_edit_topic_propagate").val() || "change_later";
            request.propagate_mode = selected_topic_propagation;
        }
        changed = true;
    }

    if (new_content !== message.raw_content && !from_topic_edited_only) {
        request.content = new_content;
        changed = true;
    }
    if (!changed) {
        // If they didn't change anything, just cancel it.
        return true;
    }
    channel.post({
        url: '/json/update_message',
        data: request,
        success: function (data) {
            if (msg_list === current_msg_list) {
                return true;
            }
        },
        error: function (xhr, error_type, xhn) {
            var message = channel.xhr_error_message("Error saving edit", xhr);
            row.find(".edit_error").text(message).show();
        }
    });
    // The message will automatically get replaced when it arrives.
};

function handle_edit_keydown(from_topic_edited_only, e) {
    var row, code = e.keyCode || e.which;

    if (e.target.id === "message_edit_content" && code === 13 &&
        (e.metaKey || e.ctrlKey)) {
        row = $(".message_edit_content").filter(":focus").closest(".message_row");
        if (message_edit.save(row, from_topic_edited_only) === true) {
            message_edit.end(row);
        }
    } else if (e.target.id === "message_edit_topic" && code === 13) {
        // Hitting enter in topic field isn't so great.
        e.stopPropagation();
        e.preventDefault();
    }
}

function edit_message (row, raw_content) {
    var content_top = row.find('.message_content')[0]
        .getBoundingClientRect().top;

    var message = current_msg_list.get(rows.id(row));
    var edit_row = row.find(".message_edit");
    var form = $(templates.render('message_edit_form',
                                  {is_stream: message.is_stream,
                                   topic: message.subject,
                                   content: raw_content}));

    var edit_obj = {form: form, raw_content: raw_content};
    var original_topic = message.subject;

    current_msg_list.show_edit_message(row, edit_obj);

    form.keydown(_.partial(handle_edit_keydown, false));

    currently_editing_messages[message.id] = edit_obj;
    if (message.type === 'stream' && message.subject === compose.empty_subject_placeholder()) {
        edit_row.find(".message_edit_topic").focus();
    } else {
        edit_row.find(".message_edit_content").focus();
    }

    // Scroll to keep the message content in the same place
    var edit_top = edit_row.find('.message_edit_content')[0]
        .getBoundingClientRect().top;

    var scroll_by = edit_top - content_top + 5 /* border and padding */;
    edit_obj.scrolled_by = scroll_by;
    viewport.scrollTop(viewport.scrollTop() + scroll_by);

    if (feature_flags.propagate_topic_edits && message.local_id === undefined) {
        var topic_input = edit_row.find(".message_edit_topic");
        topic_input.keyup( function () {
            var new_topic = topic_input.val();
            row.find('.message_edit_topic_propagate').toggle(new_topic !== original_topic);
        });
    }

    composebox_typeahead.initialize_compose_typeahead("#message_edit_content", {emoji: true});
}

function start_edit_maintaining_scroll(row, content) {
    edit_message(row, content);
    var row_bottom = row.height() + row.offset().top;
    var composebox_top = $("#compose").offset().top;
    if (row_bottom > composebox_top) {
        viewport.scrollTop(viewport.scrollTop() + row_bottom - composebox_top);
    }
}

exports.start = function (row) {
    var message = current_msg_list.get(rows.id(row));
    var msg_list = current_msg_list;
    channel.post({
        url: '/json/fetch_raw_message',
        idempotent: true,
        data: {message_id: message.id},
        success: function (data) {
            if (current_msg_list === msg_list) {
                message.raw_content = data.raw_content;
                start_edit_maintaining_scroll(row, data.raw_content);
            }
        }
    });
};

exports.start_local_failed_edit = function (row, message) {
    start_edit_maintaining_scroll(row, message.raw_content);
};

exports.start_topic_edit = function (recipient_row) {
    var form = $(templates.render('topic_edit_form'));
    current_msg_list.show_edit_topic(recipient_row, form);
    form.keydown(_.partial(handle_edit_keydown, true));
    var msg_id = rows.id_for_recipient_row(recipient_row);
    var message = current_msg_list.get(msg_id);
    var topic = message.subject;
    if (topic === compose.empty_subject_placeholder()) {
        topic = '';
    }
    form.find(".message_edit_topic").val(topic).select().focus();
};

exports.is_editing = function (id) {
    return currently_editing_messages[id] !== undefined;
};

exports.end = function (row) {
    var message = current_msg_list.get(rows.id(row));
    if (message !== undefined &&
        currently_editing_messages[message.id] !== undefined) {
        var scroll_by = currently_editing_messages[message.id].scrolled_by;
        viewport.scrollTop(viewport.scrollTop() - scroll_by);
        delete currently_editing_messages[message.id];
        current_msg_list.hide_edit_message(row);
    }
};

exports.maybe_show_edit = function (row, id) {
    if (currently_editing_messages[id] !== undefined) {
        current_msg_list.show_edit_message(row, currently_editing_messages[id]);
    }
};

$(document).on('narrow_deactivated.zulip', function (event) {
    _.each(currently_editing_messages, function (elem, idx) {
        if (current_msg_list.get(idx) !== undefined) {
            var row = current_msg_list.get_row(idx);
            current_msg_list.show_edit_message(row, elem);
        }
    });
});

return exports;
}());
