var reminder = (function () {

var exports = {};

var deferred_message_types = {
    scheduled: {
        delivery_type: 'send_later',
        test: /^\/schedule/,
        slash_command: '/schedule',
    },
    reminders: {
        delivery_type: 'remind',
        test: /^\/remind/,
        slash_command: '/remind',
    },
};

exports.deferred_message_types = deferred_message_types;

exports.is_deferred_delivery = function (message_content) {
    var reminders_test = deferred_message_types.reminders.test;
    var scheduled_test = deferred_message_types.scheduled.test;
    return reminders_test.test(message_content) ||
            scheduled_test.test(message_content);
};

function patch_request_for_scheduling(request) {
    var new_request = request;
    var raw_message = request.content.split('\n');
    var command_line = raw_message[0];
    var message = raw_message.slice(1).join('\n');

    var deferred_message_type = _.filter(deferred_message_types, function (props) {
        return command_line.match(props.test) !== null;
    })[0];
    var command = command_line.match(deferred_message_type.test)[0];

    var deliver_at = command_line.slice(command.length + 1);

    if (message.trim() === '' || deliver_at.trim() === '' ||
        command_line.slice(command.length, command.length + 1) !== ' ') {

        $("#compose-textarea").attr('disabled', false);
        if (command_line.slice(command.length, command.length + 1) !== ' ') {
            compose.compose_error(i18n.t('Invalid slash command. Check if you are missing a space after the command.'), $('#compose-textarea'));
        } else if (deliver_at.trim() === '') {
            compose.compose_error(i18n.t('Please specify a date or time'), $('#compose-textarea'));
        } else {
            compose.compose_error(i18n.t('Your reminder note is empty!'), $('#compose-textarea'));
        }
        return;
    }

    new_request.content = message;
    new_request.deliver_at = deliver_at;
    new_request.delivery_type = deferred_message_type.delivery_type;
    new_request.tz_guess = moment.tz.guess();
    return new_request;
}

function do_schedule_message(request, success, error) {

    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    request = patch_request_for_scheduling(request);

    if (request === undefined) {
        return;
    }

    transmit.send_message(request, success, error);
}

exports.schedule_message = function (request) {
    if (request === undefined) {
        request = compose.create_message_object();
    }

    var success = function (data) {
        notifications.notify_above_composebox('Scheduled your Message to be delivered at: ' + data.deliver_at);
        $("#compose-textarea").attr('disabled', false);
        compose.clear_compose_box();
    };
    var error = function (response) {
        $("#compose-textarea").attr('disabled', false);
        compose.compose_error(response, $('#compose-textarea'));
    };
    /* We are adding a disable on compose under this block because we
    want slash commands to be blocking in nature. */
    $("#compose-textarea").attr('disabled', true);

    do_schedule_message(request, success, error);
};

exports.do_set_reminder_for_message = function (msgid, timestamp) {
    var row = $("[zid='" + msgid + "']");
    function error() {
        row.find(".alert-msg")
            .text(i18n.t("Reminder not set!"))
            .css("display", "block")
            .css("color", "#b94a48")
            .delay(1000).fadeOut(300, function () {
                $(this).css("color", "");
            });
    }

    var message = current_msg_list.get(msgid);

    if (!message.raw_content) {
        var msg_list = current_msg_list;
        channel.get({
            url: '/json/messages/' + message.id,
            idempotent: true,
            success: function (data) {
                if (current_msg_list === msg_list) {
                    message.raw_content = data.raw_content;
                    exports.do_set_reminder_for_message(msgid, timestamp);
                }
            },
            error: error,
        });
        return;
    }

    var link_to_msg = narrow.by_conversation_and_time_uri(message, true);
    var command = deferred_message_types.reminders.slash_command;
    var reminder_timestamp = timestamp;
    var custom_msg = message.raw_content + '\n\n[Link to conversation](' + link_to_msg + ')';
    var reminder_msg_content = command + ' ' + reminder_timestamp + '\n' + custom_msg;
    var reminder_message = {
        type: "private",
        content: reminder_msg_content,
        sender_id: page_params.user_id,
        stream: '',
        subject: '',
    };
    var recipient = page_params.email;
    var emails = util.extract_pm_recipients(recipient);
    reminder_message.to = emails;
    reminder_message.reply_to = recipient;
    reminder_message.private_message_recipient = recipient;
    reminder_message.to_user_ids = people.email_list_to_user_ids_string(emails);

    function success() {
        row.find(".alert-msg")
            .text(i18n.t("Reminder set!"))
            .css("display", "block")
            .delay(1000).fadeOut(300);
    }

    do_schedule_message(reminder_message, success, error);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = reminder;
}

window.reminder = reminder;
