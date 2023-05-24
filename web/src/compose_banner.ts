import $ from "jquery";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_stream_does_not_exist_error from "../templates/compose_banner/stream_does_not_exist_error.hbs";

import * as blueslip from "./blueslip";
import * as compose_recipient from "./compose_recipient"; // eslint-disable-line import/no-cycle
import * as scroll_util from "./scroll_util";

export let scroll_to_message_banner_message_id: number | null = null;
export function set_scroll_to_message_banner_message_id(val: number | null): void {
    scroll_to_message_banner_message_id = val;
}

// banner types
export const WARNING = "warning";
export const ERROR = "error";

const MESSAGE_SENT_CLASSNAMES = {
    sent_scroll_to_view: "sent_scroll_to_view",
    narrow_to_recipient: "narrow_to_recipient",
    message_scheduled_success_compose_banner: "message_scheduled_success_compose_banner",
};
// Technically, unmute_topic_notification is a message sent banner, but
// it has distinct behavior / look - it has an associated action button,
// does not disappear on scroll - so we don't include it here, as it needs
// to be handled separately.

export const CLASSNAMES = {
    ...MESSAGE_SENT_CLASSNAMES,
    // unmute topic notifications are styled like warnings but have distinct behaviour
    unmute_topic_notification: "unmute_topic_notification warning-style",
    // warnings
    topic_resolved: "topic_resolved",
    recipient_not_subscribed: "recipient_not_subscribed",
    wildcard_warning: "wildcard_warning",
    private_stream_warning: "private_stream_warning",
    unscheduled_message: "unscheduled_message",
    // errors
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
    user_not_subscribed: "user_not_subscribed",
};

export function get_compose_banner_container($textarea: JQuery): JQuery {
    return $textarea.attr("id") === "compose-textarea"
        ? $("#compose_banners")
        : $textarea.closest(".message_edit_form").find(".edit_form_banners");
}

// This function provides a convenient way to add new elements
// to a banner container. The function accepts a container element
// as a parameter, to which a banner should be appended.
// Returns a boolean value indicating whether the append had succeeded.
// Cases where it would fail: when trying to append a warning banner
// when an error banner is already present.
export function append_compose_banner_to_banner_list(
    banner: HTMLElement | JQuery.htmlString,
    $list_container: JQuery,
): boolean {
    // Ensure only a single top-level element exists in the input.
    const node = parse_single_node(banner);
    // Skip rendering warning banners if the user does not have post permissions.
    if (node.hasClass(WARNING) && has_error()) {
        return false;
    }

    scroll_util.get_content_element($list_container).append(banner);
    return true;
}

export function update_or_append_banner(
    banner: HTMLElement | JQuery.htmlString,
    banner_classname: string,
    $list_container: JQuery,
): void {
    const $banner = $list_container.find(`.${CSS.escape(banner_classname)}`);
    if ($banner.length === 0) {
        append_compose_banner_to_banner_list(banner, $list_container);
    } else {
        $banner.replaceWith(banner);
    }
}

export function clear_message_sent_banners(include_unmute_banner = true): void {
    for (const classname of Object.values(MESSAGE_SENT_CLASSNAMES)) {
        $(`#compose_banners .${CSS.escape(classname)}`).remove();
    }
    if (include_unmute_banner) {
        clear_unmute_topic_notifications();
    }
    scroll_to_message_banner_message_id = null;
}

// TODO: Replace with compose_ui.hide_compose_spinner() when it is converted to ts.
function hide_compose_spinner(): void {
    $(".compose-submit-button .loader").hide();
    $(".compose-submit-button span").show();
    $(".compose-submit-button").removeClass("disable-btn");
}

export function clear_errors(): void {
    $(`#compose_banners .${CSS.escape(ERROR)}`).remove();
}

export function clear_warnings(): void {
    $(`#compose_banners .${CSS.escape(WARNING)}`).remove();
}

export function clear_uploads(): void {
    $("#compose_banners .upload_banner").remove();
}

export function clear_unmute_topic_notifications(): void {
    $(`#compose_banners .${CLASSNAMES.unmute_topic_notification.replaceAll(" ", ".")}`).remove();
}

export function clear_all(): void {
    scroll_util.get_content_element($(`#compose_banners`)).empty();
}

export function show_error_message(
    message: string,
    classname: string,
    $container: JQuery,
    $bad_input?: JQuery,
): void {
    // To prevent the same banner from appearing twice,
    // we remove the banner with a matched classname.
    $container.find(`.${CSS.escape(classname)}`).remove();

    const new_row = render_compose_banner({
        banner_type: ERROR,
        stream_id: null,
        topic_name: null,
        banner_text: message,
        button_text: null,
        classname,
    });
    append_compose_banner_to_banner_list(new_row, $container);

    hide_compose_spinner();

    if ($bad_input !== undefined) {
        $bad_input.trigger("focus").trigger("select");
    }
}

export function show_stream_does_not_exist_error(stream_name: string): void {
    // Remove any existing banners with this warning.
    $(`#compose_banners .${CSS.escape(CLASSNAMES.stream_does_not_exist)}`).remove();

    const new_row = render_stream_does_not_exist_error({
        banner_type: ERROR,
        stream_name,
        classname: CLASSNAMES.stream_does_not_exist,
    });
    append_compose_banner_to_banner_list(new_row, $("#compose_banners"));
    hide_compose_spinner();

    // Open stream select dropdown.
    $("#compose_select_recipient_widget").trigger("click");
}

// Ensure the input has only one single top-level element,
// and return a JQuery element of it.
function parse_single_node(
    html_element: HTMLElement | JQuery.htmlString,
): JQuery<Node | HTMLElement> {
    if (typeof html_element === "string") {
        const nodes = $.parseHTML(html_element.trim());
        if (nodes.length === 0 || nodes.length > 1) {
            blueslip.error("HTML string input can only contain one top-level element.");
        }
        return $(nodes[0]);
    }
    return $(html_element);
}

export function has_error(): boolean {
    return compose_recipient.get_posting_policy_error_message() !== "";
}
