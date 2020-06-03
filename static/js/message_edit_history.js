const render_message_edit_history = require('../templates/message_edit_history.hbs');

exports.fetch_and_render_message_history = function (message) {
    channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {message_id: JSON.stringify(message.id)},
        success: function (data) {
            const content_edit_history = [];
            let prev_timestamp;

            for (const [index, msg] of data.message_history.entries()) {
                // Format timestamp nicely for display
                const timestamp = timerender.get_full_time(msg.timestamp);
                const item = {
                    timestamp: moment(timestamp).format("h:mm A"),
                    display_date: moment(timestamp).format("MMMM D, YYYY"),
                };
                if (msg.user_id) {
                    const person = people.get_by_user_id(msg.user_id);
                    item.edited_by = person.full_name;
                }

                if (index === 0) {
                    item.posted_or_edited = "Posted by";
                    item.body_to_render = msg.rendered_content;
                    item.show_date_row = true;
                } else if (msg.prev_topic && msg.prev_content) {
                    item.posted_or_edited = "Edited by";
                    item.body_to_render = msg.content_html_diff;
                    item.show_date_row = !moment(timestamp).isSame(prev_timestamp, 'day');
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                } else if (msg.prev_topic) {
                    item.posted_or_edited = "Topic edited by";
                    item.show_date_row = !moment(timestamp).isSame(prev_timestamp, 'day');
                    item.topic_edited = true;
                    item.prev_topic = msg.prev_topic;
                    item.new_topic = msg.topic;
                } else {
                    // just a content edit
                    item.posted_or_edited = "Edited by";
                    item.body_to_render = msg.content_html_diff;
                    item.show_date_row = !moment(timestamp).isSame(prev_timestamp, 'day');
                }

                content_edit_history.push(item);

                prev_timestamp = timestamp;
            }
            $('#message-history').attr('data-message-id', message.id);
            $('#message-history').html(render_message_edit_history({
                edited_messages: content_edit_history,
            }));
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error fetching message edit history"), xhr,
                            $("#message-history-error"));
        },
    });
};

exports.show_history = function (message) {
    $('#message-history').html('');
    $('#message-edit-history').modal("show");
    exports.fetch_and_render_message_history(message);
};

window.message_edit_history = exports;
