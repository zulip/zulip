"use strict";

const people = require("./people");

exports.input_field = function () {
    return $(".user_status_overlay input.user_status");
};

exports.submit_button = function () {
    return $(".user_status_overlay .set_user_status");
};

exports.open_overlay = function () {
    const overlay = $(".user_status_overlay");
    overlays.open_overlay({
        name: "user_status_overlay",
        overlay,
        on_close() {},
    });

    const user_id = people.my_current_user_id();
    const old_status_text = user_status.get_status_text(user_id);
    const field = exports.input_field();
    field.val(old_status_text);
    field.trigger("select");
    field.trigger("focus");
    exports.toggle_clear_message_button();

    const button = exports.submit_button();
    button.prop("disabled", true);
};

exports.close_overlay = function () {
    overlays.close_overlay("user_status_overlay");
};

exports.submit_new_status = function () {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) || "";
    old_status_text = old_status_text.trim();
    const new_status_text = exports.input_field().val().trim();

    if (old_status_text === new_status_text) {
        exports.close_overlay();
        return;
    }

    user_status.server_update({
        status_text: new_status_text,
        success() {
            exports.close_overlay();
        },
    });
};

exports.update_button = function () {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) || "";
    old_status_text = old_status_text.trim();
    const new_status_text = exports.input_field().val().trim();
    const button = exports.submit_button();

    if (old_status_text === new_status_text) {
        button.prop("disabled", true);
    } else {
        button.prop("disabled", false);
    }
};

exports.toggle_clear_message_button = function () {
    if (exports.input_field().val() !== "") {
        $("#clear_status_message_button").prop("disabled", false);
    } else {
        $("#clear_status_message_button").prop("disabled", true);
    }
};

exports.clear_message = function () {
    const field = exports.input_field();
    field.val("");
    $("#clear_status_message_button").prop("disabled", true);
};

exports.initialize = function () {
    $("body").on("click", ".user_status_overlay .set_user_status", () => {
        exports.submit_new_status();
    });

    $("body").on("keypress", ".user_status_overlay .user_status", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();

            exports.submit_new_status();
        }
    });

    $("body").on("keyup", ".user_status_overlay input.user_status", () => {
        exports.update_button();
        exports.toggle_clear_message_button();
    });

    $("#clear_status_message_button").on("click", () => {
        exports.clear_message();
        exports.update_button();
    });
};

window.user_status_ui = exports;
