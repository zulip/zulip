import $ from "jquery";

import * as common from "./common";

export function show(error_html, bad_input, alert_class = "alert-error") {
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass(alert_class)
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").html(error_html);
    $("#compose-send-button").prop("disabled", false);
    $("#sending-indicator").hide();
    if (bad_input !== undefined) {
        bad_input.trigger("focus").trigger("select");
    }
}

export function show_not_subscribed(error_html, bad_input) {
    show(error_html, bad_input, "home-error-bar");
    $(".compose-send-status-close").hide();
}

export function hide() {
    $("#compose-send-status").stop(true).fadeOut(500);
}
