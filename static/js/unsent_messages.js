import $ from "jquery";

import render_compose_unsent_message from "../templates/compose_unsent_message.hbs";

import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_state from "./compose_state";
import {localstorage} from "./localstorage";

export const unsent_messages = (function () {
    let messages_to_send = [];
    const exports = {};

    // the key that the unsent messages are stored under.
    const KEY = "unsent_messages";
    const ls = localstorage();
    ls.version = 1;

    function getTimestamp() {
        return Date.now();
    }

    function save(unsent_messages) {
        ls.set(KEY, unsent_messages);
    }

    exports.getUnsentMessages = function () {
        messages_to_send = ls.get(KEY) || [];
        return messages_to_send;
    };

    exports.addUnsentMessage = function (unsent_message) {
        const unsent_messages = exports.getUnsentMessages();
        unsent_message.createdAt = getTimestamp();
        unsent_messages.push(unsent_message);
        save(unsent_messages);
    };

    exports.removeUnsentMessages = function () {
        const unsent_messages = [];
        save(unsent_messages);
    };

    exports.sort_messages = function () {
        messages_to_send.sort((msg_a, msg_b) => msg_b.createdAt - msg_a.createdAt);
    };

    exports.next = function () {
        return messages_to_send.pop();
    };

    exports.is_empty = function () {
        if (messages_to_send.length === 0) {
            return true;
        }
        return false;
    };

    return exports;
})();

export function store_unsent_message(message_content) {
    const message = compose_state.construct_message_data(message_content);
    unsent_messages.addUnsentMessage(message);
}

function start_compose_actions() {
    const message = unsent_messages.next();
    if (message === undefined) {
        // This implies that we have no unsent messages left.
        return;
    }

    compose_actions.start(message.type, {
        stream: message.stream || "",
        topic: message.topic || "",
        private_message_recipient: message.private_message_recipient || "",
        content: message.content || "",
    });

    const unsent_message_template = render_compose_unsent_message();
    const unsent_message_warning_area = $("#compose-unsent-message");

    // Show only one warning message for any unsent messages.
    if (!unsent_message_warning_area.is(":visible")) {
        unsent_message_warning_area.append(unsent_message_template);
    }

    unsent_message_warning_area.show();
    // We want the user to acknowledge these messages through the template.
    $("#compose-send-button").prop("disabled", true);
}

function clear_unsent_message_warning(event) {
    $(event.target).parents(".compose-unsent-message").remove();
    $("#compose-unsent-message").hide();
    $("#compose-unsent-message").empty();
    $("#compose-send-status").hide();
    $("#compose-send-button").prop("disabled", false);
}

export function send_unsent_messages() {
    // We sent these messages in the order they were created.
    unsent_messages.sort_messages();

    start_compose_actions();

    $("#compose-unsent-message").on("click", ".compose-unsent-message-confirm", (event) => {
        event.preventDefault();

        compose.finish();
        if (unsent_messages.is_empty()) {
            clear_unsent_message_warning(event);
        } else {
            start_compose_actions();
        }
    });

    $("#compose-unsent-message").on("click", ".compose-unsent-message-cancel", (event) => {
        event.preventDefault();

        compose.clear_compose_box();
        if (unsent_messages.is_empty()) {
            clear_unsent_message_warning(event);
        } else {
            start_compose_actions();
        }
    });
}

export function get_unsent_messages() {
    return unsent_messages.getUnsentMessages();
}

export function initialize() {
    get_unsent_messages();
    // We remove the unsent messages so that the old unsent
    // messages don't clutter up in the localStorage.
    unsent_messages.removeUnsentMessages();
    send_unsent_messages();
}
