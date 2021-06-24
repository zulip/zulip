import $ from "jquery";

import render_set_status_overlay from "../templates/set_status_overlay.hbs";

import * as overlays from "./overlays";
import * as people from "./people";
import * as user_status from "./user_status";

export function input_field() {
    return $("#set_user_status_modal input.user_status");
}

export function submit_button() {
    return $("#set_user_status_modal .set_user_status");
}

export function open_user_status_modal() {
    const rendered_set_status_overlay = render_set_status_overlay();
    $(".app").append(rendered_set_status_overlay);

    overlays.open_modal("#set_user_status_modal", {autoremove: true});

    const user_id = people.my_current_user_id();
    const old_status_text = user_status.get_status_text(user_id);
    const field = input_field();
    field.val(old_status_text);
    field.trigger("select");
    field.trigger("focus");
    toggle_clear_message_button();

    const button = submit_button();
    button.prop("disabled", true);
}

export function close_user_status_modal() {
    overlays.close_modal("#set_user_status_modal");
}

export function submit_new_status() {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) || "";
    old_status_text = old_status_text.trim();
    const new_status_text = input_field().val().trim();

    if (old_status_text === new_status_text) {
        close_user_status_modal();
        return;
    }

    user_status.server_update({
        status_text: new_status_text,
        success() {
            close_user_status_modal();
        },
    });
}

export function update_button() {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) || "";
    old_status_text = old_status_text.trim();
    const new_status_text = input_field().val().trim();
    const button = submit_button();

    if (old_status_text === new_status_text) {
        button.prop("disabled", true);
    } else {
        button.prop("disabled", false);
    }
}

export function toggle_clear_message_button() {
    if (input_field().val() !== "") {
        $("#clear_status_message_button").prop("disabled", false);
    } else {
        $("#clear_status_message_button").prop("disabled", true);
    }
}

export function clear_message() {
    const field = input_field();
    field.val("");
    $("#clear_status_message_button").prop("disabled", true);
}

export function initialize() {
    $("body").on("click", ".user-status-value", (event) => {
        event.stopPropagation();
        const user_status_value = $(event.currentTarget).text();
        $("input.user_status").val(user_status_value);
        toggle_clear_message_button();
        update_button();
    });

    $("body").on("click", "#set_user_status_modal .set_user_status", () => {
        submit_new_status();
    });

    $("body").on("keypress", "#set_user_status_modal .user_status", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();

            submit_new_status();
        }
    });

    $("body").on("keyup", "#set_user_status_modal input.user_status", () => {
        update_button();
        toggle_clear_message_button();
    });

    $("body").on("click", "#clear_status_message_button", () => {
        clear_message();
        update_button();
    });
}
