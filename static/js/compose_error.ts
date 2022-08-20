import $ from "jquery";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_stream_does_not_exist_error from "../templates/compose_banner/stream_does_not_exist_error.hbs";

import * as common from "./common";

// banner types
export const WARNING = "warning";
export const ERROR = "error";

export const CLASSNAMES = {
    // warnings
    topic_resolved: "topic_resolved",
    recipient_not_subscribed: "recipient_not_subscribed",
    wildcard_warning: "wildcard_warning",
    // errors
    empty_message: "empty_message",
    wildcards_not_allowed: "wildcards_not_allowed",
    subscription_error: "subscription_error",
    stream_does_not_exist: "stream_does_not_exist",
    missing_stream: "missing_stream",
    no_post_permissions: "no_post_permissions",
    private_messages_disabled: "private_messages_disabled",
    missing_private_message_recipient: "missing_private_message_recipient",
    invalid_recipient: "invalid_recipient",
    invalid_recipients: "invalid_recipients",
    deactivated_user: "deactivated_user",
    message_too_long: "message_too_long",
    topic_missing: "topic_missing",
    zephyr_not_running: "zephyr_not_running",
    generic_compose_error: "generic_compose_error",
};

// TODO: Replace with compose_ui.hide_compose_spinner() when it is converted to ts.
function hide_compose_spinner(): void {
    $("#compose-send-button .loader").hide();
    $("#compose-send-button span").show();
    $("#compose-send-button").removeClass("disable-btn");
}

export function show_error_message(message: string, classname: string, $bad_input?: JQuery): void {
    $(`#compose_banners .${classname}`).remove();

    const new_row = render_compose_banner({
        banner_type: ERROR,
        stream_id: null,
        topic_name: null,
        banner_text: message,
        button_text: null,
        classname,
    });
    const $compose_banner_area = $("#compose_banners");
    $compose_banner_area.append(new_row);

    hide_compose_spinner();

    if ($bad_input !== undefined) {
        $bad_input.trigger("focus").trigger("select");
    }
}

export function show(error_html: string, $bad_input?: JQuery, alert_class = "alert-error"): void {
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass(alert_class)
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").html(error_html);
    hide_compose_spinner();

    if ($bad_input !== undefined) {
        $bad_input.trigger("focus").trigger("select");
    }
}

export function show_stream_does_not_exist_error(stream_name: string): void {
    // Remove any existing banners with this warning.
    $(`#compose_banners .${CLASSNAMES.stream_does_not_exist}`).remove();

    const new_row = render_stream_does_not_exist_error({
        banner_type: ERROR,
        stream_name,
        classname: CLASSNAMES.stream_does_not_exist,
    });
    const $compose_banner_area = $("#compose_banners");
    $compose_banner_area.append(new_row);
    hide_compose_spinner();
    $("#stream_message_recipient_stream").trigger("focus").trigger("select");
}

export function show_not_subscribed(error_html: string, $bad_input?: JQuery): void {
    show(error_html, $bad_input, "home-error-bar");
    $(".compose-send-status-close").hide();
}

export function hide(): void {
    $("#compose-send-status").stop(true).fadeOut(500);
}
