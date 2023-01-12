import $ from "jquery";

import * as channel from "./channel";
import * as compose from "./compose";
import * as compose_banner from "./compose_banner";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as message_lists from "./message_lists";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as people from "./people";
import * as transmit from "./transmit";
import * as util from "./util";

export const deferred_message_types = {
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

export function is_deferred_delivery(message_content) {
    const reminders_test = deferred_message_types.reminders.test;
    const scheduled_test = deferred_message_types.scheduled.test;
    return reminders_test.test(message_content) || scheduled_test.test(message_content);
}

export function patch_request_for_scheduling(request, message_content, deliver_at, delivery_type) {
    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    const new_request = request;
    new_request.content = message_content;
    new_request.deliver_at = deliver_at;
    new_request.delivery_type = delivery_type;
    new_request.tz_guess = new Intl.DateTimeFormat().resolvedOptions().timeZone;
    return new_request;
}

export function schedule_message(request = compose.create_message_object()) {
    const raw_message = request.content.split("\n");
    const command_line = raw_message[0];
    const message = raw_message.slice(1).join("\n");

    const deferred_message_type = Object.values(deferred_message_types).find(
        (props) => command_line.match(props.test) !== null,
    );
    const command = command_line.match(deferred_message_type.test)[0];

    const deliver_at = command_line.slice(command.length + 1);

    let error_message;
    if (command_line.slice(command.length, command.length + 1) !== " ") {
        error_message = $t({
            defaultMessage:
                "Invalid slash command. Check if you are missing a space after the command.",
        });
    } else if (deliver_at.trim() === "") {
        error_message = $t({defaultMessage: "Please specify a date or time."});
    } else if (message.trim() === "") {
        error_message = $t({defaultMessage: "You have nothing to send!"});
    }

    if (error_message) {
        compose_banner.show_error_message(
            error_message,
            compose_banner.CLASSNAMES.generic_compose_error,
            $("#compose-textarea"),
        );
        $("#compose-textarea").prop("disabled", false);
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
            const deliver_at = data.deliver_at;
            notifications.notify_above_composebox(
                $t_html({defaultMessage: `Message scheduled for {deliver_at}`}, {deliver_at}),
            );
        }
        $("#compose-textarea").prop("disabled", false);
        compose.clear_compose_box();
    };
    const error = function (response) {
        $("#compose-textarea").prop("disabled", false);
        compose_banner.show_error_message(
            response,
            compose_banner.CLASSNAMES.generic_compose_error,
            $("#compose-textarea"),
        );
    };
    /* We are adding a disable on compose under this block because we
    want slash commands to be blocking in nature. */
    $("#compose-textarea").prop("disabled", true);

    const future_message = true;
    transmit.send_message(request, success, error, future_message);
}

export function do_set_reminder_for_message(message_id, timestamp) {
    const $row = $(`[zid='${CSS.escape(message_id)}']`);
    function error() {
        $row.find(".alert-msg")
            .text($t({defaultMessage: "Reminder not set!"}))
            .css("display", "block")
            .css("color", "#b94a48")
            .delay(1000)
            .fadeOut(300, function () {
                $(this).css("color", "");
            });
    }

    const message = message_lists.current.get(message_id);

    if (!message.raw_content) {
        const msg_list = message_lists.current;
        channel.get({
            url: "/json/messages/" + message.id,
            success(data) {
                if (message_lists.current === msg_list) {
                    message.raw_content = data.raw_content;
                    do_set_reminder_for_message(message_id, timestamp);
                }
            },
            error,
        });
        return;
    }

    const link_to_msg = hash_util.by_conversation_and_time_url(message);
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
        $row.find(".alert-msg")
            .text($t({defaultMessage: "Reminder set!"}))
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
}
