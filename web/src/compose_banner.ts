import $ from "jquery";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_stream_does_not_exist_error from "../templates/compose_banner/stream_does_not_exist_error.hbs";

import {$t} from "./i18n";
import * as scroll_util from "./scroll_util";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";

export let scroll_to_message_banner_message_id: number | null = null;
export function set_scroll_to_message_banner_message_id(val: number | null): void {
    scroll_to_message_banner_message_id = val;
}

// banner types
export const WARNING = "warning";
export const ERROR = "error";
export const SUCCESS = "success";
export const INFO = "info";

const MESSAGE_SENT_CLASSNAMES = {
    sent_scroll_to_view: "sent_scroll_to_view",
    narrow_to_recipient: "narrow_to_recipient",
    message_scheduled_success_compose_banner: "message_scheduled_success_compose_banner",
    automatic_new_visibility_policy: "automatic_new_visibility_policy",
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
    search_view: "search_view",
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
export function append_compose_banner_to_banner_list(
    $banner: JQuery,
    $list_container: JQuery,
): void {
    scroll_util.get_content_element($list_container).append($banner);
}

export function update_or_append_banner(
    $banner: JQuery,
    banner_classname: string,
    $list_container: JQuery,
): void {
    const $existing_banner = $list_container.find(`.${CSS.escape(banner_classname)}`);
    if ($existing_banner.length === 0) {
        append_compose_banner_to_banner_list($banner, $list_container);
    } else {
        $existing_banner.replaceWith($banner);
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
    $(
        `#compose_banners .${CLASSNAMES.unmute_topic_notification
            .split(" ")
            .map((classname) => CSS.escape(classname))
            .join(".")}`,
    ).remove();
}

export function clear_search_view_banner(): void {
    $(`#compose_banners .${CSS.escape(CLASSNAMES.search_view)}`).remove();
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
    // Important: This API intentionally does not support passing an
    // HTML message; doing so creates unnecessary XSS risk. If you
    // want HTML in your compose banner, use a partial subclassing
    // compose_banner and the append_compose_banner_to_banner_list
    // API; See, for example, automatic_new_visibility_policy_banner.
    //
    // To prevent the same banner from appearing twice,
    // we remove the banner with a matched classname.
    $container.find(`.${CSS.escape(classname)}`).remove();

    const new_row_html = render_compose_banner({
        banner_type: ERROR,
        stream_id: null,
        topic_name: null,
        banner_text: message,
        button_text: null,
        classname,
    });
    append_compose_banner_to_banner_list($(new_row_html), $container);

    hide_compose_spinner();

    if ($bad_input !== undefined) {
        $bad_input.trigger("focus").trigger("select");
    }
}

export function show_stream_does_not_exist_error(stream_name: string): void {
    // Remove any existing banners with this warning.
    $(`#compose_banners .${CSS.escape(CLASSNAMES.stream_does_not_exist)}`).remove();

    const new_row_html = render_stream_does_not_exist_error({
        banner_type: ERROR,
        channel_name: stream_name,
        classname: CLASSNAMES.stream_does_not_exist,
    });
    append_compose_banner_to_banner_list($(new_row_html), $("#compose_banners"));
    hide_compose_spinner();

    // Open stream select dropdown.
    $("#compose_select_recipient_widget").trigger("click");
}

export function show_stream_not_subscribed_error(sub: StreamSubscription): void {
    const $banner_container = $("#compose_banners");
    if ($(`#compose_banners .${CSS.escape(CLASSNAMES.user_not_subscribed)}`).length) {
        return;
    }
    const new_row_html = render_compose_banner({
        banner_type: ERROR,
        banner_text: $t({
            defaultMessage:
                "You're not subscribed to this channel. You will not be notified if other users reply to your message.",
        }),
        button_text: stream_data.can_toggle_subscription(sub)
            ? $t({defaultMessage: "Subscribe"})
            : null,
        classname: CLASSNAMES.user_not_subscribed,
        // The message cannot be sent until the user subscribes to the stream, so
        // closing the banner would be more confusing than helpful.
        hide_close_button: true,
    });
    append_compose_banner_to_banner_list($(new_row_html), $banner_container);
}
