"use strict";

const moment = require("moment-timezone");

const people = require("./people");
const util = require("./util");

const deferred_message_types = {
    scheduled: {
        delivery_type: "send_later",
        test: /^\/schedule/,
        slash_command: "/schedule",
    },
    reminders: {
        delivery_type: "remind",
        test: /^\/remind/,
        slash_command: "/remind",
    },
};

exports.deferred_message_types = deferred_message_types;

exports.is_deferred_delivery = function (message_content) {
    const reminders_test = deferred_message_types.reminders.test;
    const scheduled_test = deferred_message_types.scheduled.test;
    return reminders_test.test(message_content) || scheduled_test.test(message_content);
};

function patch_request_for_scheduling(request, message_content, deliver_at, delivery_type) {
    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    const new_request = request;
    new_request.content = message_content;
    new_request.deliver_at = deliver_at;
    new_request.delivery_type = delivery_type;
    new_request.tz_guess = moment.tz.guess();
    return new_request;
}

exports.schedule_message = function (request) {
    if (request === undefined) {
        request = compose.create_message_object();
    }

    const raw_message = request.content.split("\n");
    const command_line = raw_message[0];
    const message = raw_message.slice(1).join("\n");

    const deferred_message_type = deferred_message_types.filter(
        (props) => command_line.match(props.test) !== null,
    )[0];
    const command = command_line.match(deferred_message_type.test)[0];

    const deliver_at = command_line.slice(command.length + 1);

    if (
        message.trim() === "" ||
        deliver_at.trim() === "" ||
        command_line.slice(command.length, command.length + 1) !== " "
    ) {
        $("#compose-textarea").prop("disabled", false);
        if (command_line.slice(command.length, command.length + 1) !== " ") {
            compose.compose_error(
                i18n.t(
                    "Invalid slash command. Check if you are missing a space after the command.",
                ),
                $("#compose-textarea"),
            );
        } else if (deliver_at.trim() === "") {
            compose.compose_error(i18n.t("Please specify a date or time"), $("#compose-textarea"));
        } else {
            compose.compose_error(i18n.t("Your reminder note is empty!"), $("#compose-textarea"));
        }
        return;
    }

    request = patch_request_for_scheduling(
        request,
        message,
        deliver_at,
        deferred_message_type.delivery_type,
    );

    const success = function (data) {
        if (request.delivery_type === deferred_message_types.scheduled.delivery_type) {
            notifications.notify_above_composebox(
                "Scheduled your Message to be delivered at: " + data.deliver_at,
            );
        }
        $("#compose-textarea").prop("disabled", false);
        compose.clear_compose_box();
    };
    const error = function (response) {
        $("#compose-textarea").prop("disabled", false);
        compose.compose_error(response, $("#compose-textarea"));
    };
    /* We are adding a disable on compose under this block because we
    want slash commands to be blocking in nature. */
    $("#compose-textarea").prop("disabled", true);

    transmit.send_message(request, success, error);
};

exports.do_set_reminder_for_message = function (message_id, timestamp) {
    const row = $("[zid='" + message_id + "']");
    function error() {
        row.find(".alert-msg")
            .text(i18n.t("Reminder not set!"))
            .css("display", "block")
            .css("color", "#b94a48")
            .delay(1000)
            .fadeOut(300, function () {
                $(this).css("color", "");
            });
    }

    const message = current_msg_list.get(message_id);

    if (!message.raw_content) {
        const msg_list = current_msg_list;
        channel.get({
            url: "/json/messages/" + message.id,
            idempotent: true,
            success(data) {
                if (current_msg_list === msg_list) {
                    message.raw_content = data.raw_content;
                    exports.do_set_reminder_for_message(message_id, timestamp);
                }
            },
            error,
        });
        return;
    }

    const link_to_msg = hash_util.by_conversation_and_time_uri(message);
    const reminder_msg_content =
        message.raw_content + "\n\n[Link to conversation](" + link_to_msg + ")";
    let reminder_message = {
        type: "private",
        sender_id: page_params.user_id,
        stream: "",
    };
    reminder_message.topic = "";

    const recipient = page_params.email;
    const emails = util.extract_pm_recipients(recipient);
    reminder_message.to = emails;
    reminder_message.reply_to = recipient;
    reminder_message.private_message_recipient = recipient;
    reminder_message.to_user_ids = people.email_list_to_user_ids_string(emails);

    function success() {
        row.find(".alert-msg")
            .text(i18n.t("Reminder set!"))
            .css("display", "block")
            .delay(1000)
            .fadeOut(300);
    }

    reminder_message = patch_request_for_scheduling(
        reminder_message,
        reminder_msg_content,
        timestamp,
        deferred_message_types.reminders.delivery_type,
    );
    transmit.send_message(reminder_message, success, error);
};

window.reminder = exports;
