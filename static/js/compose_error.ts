import $ from "jquery";

import * as common from "./common";

// banner types
export const WARNING = "warning";

export const CLASSNAMES = {
    // warnings
    topic_resolved: "topic_resolved",
};

export function show(error_html: string, $bad_input?: JQuery, alert_class = "alert-error"): void {
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass(alert_class)
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").html(error_html);
    // TODO: Replace with compose_ui.hide_compose_spinner() when it is converted to ts.
    $("#compose-send-button .loader").hide();
    $("#compose-send-button span").show();
    $("#compose-send-button").removeClass("disable-btn");

    if ($bad_input !== undefined) {
        $bad_input.trigger("focus").trigger("select");
    }
}

export function show_not_subscribed(error_html: string, $bad_input?: JQuery): void {
    show(error_html, $bad_input, "home-error-bar");
    $(".compose-send-status-close").hide();
}

export function hide(): void {
    $("#compose-send-status").stop(true).fadeOut(500);
}
