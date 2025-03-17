import $ from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import * as buttons from "./buttons.ts";
import {$t} from "./i18n.ts";

function fade_out_popup_banner($banner: JQuery): void {
    $banner.addClass("fade-out");
    // The delay is the same as the animation duration for fade-out.
    setTimeout(() => {
        banners.close($banner);
    }, 300);
}

const CONNECTION_ERROR_POPUP_BANNER: Banner = {
    intent: "danger",
    label: $t({
        defaultMessage: "Unable to connect to Zulip. Retrying soon…",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Try now"}),
            custom_classes: "retry-connection",
        },
    ],
    close_button: true,
    custom_classes: "connection-error-banner popup-banner",
};

// Show user a banner with a button to allow user to navigate
// to the first unread if required.
const FOUND_MISSING_UNREADS_IN_CURRENT_NARROW: Banner = {
    intent: "warning",
    label: $t({
        defaultMessage: "This conversation also has older unread messages.",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Jump to first unread"}),
            custom_classes: "found-missing-unreads-jump-to-first-unread",
        },
    ],
    close_button: true,
    custom_classes: "found-missing-unreads popup-banner",
};

export function open_found_missing_unreads_banner(on_jump_to_first_unread: () => void): void {
    banners.append(FOUND_MISSING_UNREADS_IN_CURRENT_NARROW, $("#popup_banners_wrapper"));

    $("#popup_banners_wrapper").on(
        "click",
        ".found-missing-unreads-jump-to-first-unread",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();

            const $banner = $(this).closest(".banner");
            fade_out_popup_banner($banner);
            on_jump_to_first_unread();
        },
    );
}

export function close_found_missing_unreads_banner(): void {
    const $banner = $("#popup_banners_wrapper").find(".found-missing-unreads");
    if ($banner.length === 0) {
        return;
    }

    fade_out_popup_banner($banner);
}

export function open_connection_error_popup_banner(opts: {
    on_retry_callback: () => void;
    is_get_events_error?: boolean;
}): void {
    // If the banner is already open, don't open it again, and instead remove
    // the loading indicator on the retry button, if it was being shown.
    const $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    if ($banner.length > 0) {
        const $retry_connection_button = $banner.find(".retry-connection");
        if ($retry_connection_button.find(".button-loading-indicator").length > 0) {
            // Add some delay before hiding the loading indicator, to visually
            // indicate that the retry sequence was executed again but failed.
            setTimeout(() => {
                buttons.hide_button_loading_indicator($retry_connection_button);
            }, 1000);
        }
        return;
    }
    // Prevent the interference between the server errors from
    // get_events in web/src/server_events.js and the one from
    // load_messages in web/src/message_fetch.ts.
    if (opts.is_get_events_error) {
        CONNECTION_ERROR_POPUP_BANNER.custom_classes += " get-events-error";
    }
    banners.append(CONNECTION_ERROR_POPUP_BANNER, $("#popup_banners_wrapper"));

    $("#popup_banners_wrapper").on("click", ".retry-connection", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();

        buttons.show_button_loading_indicator($(this));
        opts.on_retry_callback();
    });
}

export function close_connection_error_popup_banner(check_if_get_events_error = false): void {
    const $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    if ($banner.length === 0) {
        return;
    }
    if (check_if_get_events_error && $banner.hasClass("get-events-error")) {
        return;
    }
    fade_out_popup_banner($banner);
}

export function initialize(): void {
    $("#popup_banners_wrapper").on(
        "click",
        ".banner-close-action",
        function (this: HTMLElement, e) {
            // Override the banner close event listener in web/src/banners.ts,
            // to add a fade-out animation when the banner is closed.
            e.preventDefault();
            e.stopPropagation();
            const $banner = $(this).closest(".banner");
            fade_out_popup_banner($banner);
        },
    );
}
