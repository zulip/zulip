var message_edit = (function () {
var exports = {};
var currently_editing_messages = {};


//returns true if the edit task should end.
exports.save = function (row) {
    var msg_list = current_msg_list;
    var message = current_msg_list.get(rows.id(row));
    var changed = false;

    var request = {message_id: message.id};
    if (message.type === "stream") {
        var new_topic = row.find(".message_edit_topic").val();
        if (new_topic !== message.subject && new_topic.trim() !== "") {
            request.subject = new_topic;

            if (feature_flags.propagate_topic_edits) {
                var selected_topic_propagation = row.find("select.message_edit_topic_propagate").val() || "change_later";
                request.propagate_mode = selected_topic_propagation;
            }
            changed = true;
        }
    }

    var new_content = row.find(".message_edit_content").val();
    if (new_content !== message.raw_content) {
        request.content = new_content;
        changed = true;
    }
    if (!changed) {
        // If they didn't change anything, just cancel it.
        return true;
    }
    $.ajax({
        type: 'POST',
        url: '/json/update_message',
        data: request,
        dataType: 'json',
        success: function (data) {
            if (msg_list === current_msg_list) {
                return true;
            }
        },
        error: function (xhr, error_type, xhn) {
            var message = util.xhr_error_message("Error saving edit", xhr);
            row.find(".edit_error").text(message).show();
        }
    });
    // The message will automatically get replaced when it arrives.
};

function handle_edit_keydown(e) {
    var row, code = e.keyCode || e.which;

    if (e.target.id === "message_edit_content" && code === 13 &&
        (e.metaKey || e.ctrlKey || (page_params.enter_sends && !e.shiftKey))) {
        e.preventDefault();

        row = $(".message_edit_content").filter(":focus").closest(".message_row");
        if (message_edit.save(row) === true) {
            message_edit.end(row);
        }
    } else if (e.target.id === "message_edit_topic" && code === 13) {
        //hitting enter in topic field isn't so great.
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

    form.keydown(handle_edit_keydown);

    currently_editing_messages[message.id] = edit_obj;
    if (message.subject === compose.empty_subject_placeholder()) {
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

    if (feature_flags.propagate_topic_edits) {
        var topic_input = edit_row.find(".message_edit_topic");
        topic_input.keyup( function () {
            var new_topic = topic_input.val();
            row.find('.message_edit_topic_propagate').toggle(new_topic !== original_topic);
        });
    }

    composebox_typeahead.initialize_compose_typeahead("#message_edit_content", {emoji: true});
}

exports.start = function (row) {
    var message = current_msg_list.get(rows.id(row));
    var msg_list = current_msg_list;
    $.ajax({
        type: 'POST',
        url: '/json/fetch_raw_message',
        data: {message_id: message.id},
        dataType: 'json',
        success: function (data) {
            if (current_msg_list === msg_list) {
                message.raw_content = data.raw_content;
                edit_message(row, data.raw_content);
            }
        }
    });
};

exports.start_topic_edit = function (recipient_row) {
    var form = $(templates.render('topic_edit_form'));
    current_msg_list.show_edit_topic(recipient_row, form);
    form.keydown(handle_edit_keydown);
    form.find(".message_edit_topic").focus();
};

exports.is_editing = function (id) {
    return currently_editing_messages[id] !== undefined;
};

exports.end = function (row) {
    var message = current_msg_list.get(rows.id(row));
    if (currently_editing_messages[message.id] !== undefined) {
        var scroll_by = currently_editing_messages[message.id].scrolled_by;
        viewport.scrollTop(viewport.scrollTop() - scroll_by);
        delete currently_editing_messages[message.id];
        current_msg_list.hide_edit_message(row);
    }
};

exports.maybe_show_edit = function (row, id) {
    if (currently_editing_messages[id] !== undefined){
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
