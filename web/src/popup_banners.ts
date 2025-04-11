import $ from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import * as buttons from "./buttons.ts";
import {$t} from "./i18n.ts";

export type ReloadingReason = "reload" | "update";

let retry_connection_interval: ReturnType<typeof setInterval> | undefined;
let original_retry_delay_secs = 0;

function fade_out_popup_banner($banner: JQuery): void {
    $banner.addClass("fade-out");
    // The delay is the same as the animation duration for fade-out.
    setTimeout(() => {
        banners.close($banner);
    }, 300);
}

const get_connection_error_label = (retry_delay_secs: number): string => {
    if (original_retry_delay_secs < 5) {
        // When the retry delay is less than 5 seconds, we don't show the retry
        // delay time in the banner, and instead just show "Trying to reconnect soon…"
        // to avoid constant flickering of the banner label for very short times.
        return $t({defaultMessage: "Unable to connect to Zulip. Trying to reconnect soon…"});
    }
    return $t(
        {
            defaultMessage:
                "Unable to connect to Zulip. {retry_delay_secs, plural, one {Trying to reconnect in {retry_delay_secs} second…} other {Trying to reconnect in {retry_delay_secs} seconds…}}",
        },
        {retry_delay_secs},
    );
};

const connection_error_popup_banner = (retry_seconds: number): Banner => ({
    intent: "danger",
    label: get_connection_error_label(retry_seconds),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Try now"}),
            custom_classes: "retry-connection",
        },
    ],
    close_button: true,
    custom_classes: "connection-error-banner popup-banner",
});

const update_connection_error_banner = ($banner: JQuery, retry_delay_secs: number): void => {
    original_retry_delay_secs = retry_delay_secs;
    if (retry_connection_interval !== undefined) {
        clearInterval(retry_connection_interval);
    }
    const $banner_label = $banner.find(".banner-label");
    retry_connection_interval = setInterval(() => {
        retry_delay_secs -= 1;
        if (retry_delay_secs <= 0) {
            // When the retry delay is over, stop the retry interval.
            clearInterval(retry_connection_interval);
            return;
        }
        if (retry_delay_secs <= 1) {
            // One second before the retry, show the loading indicator to
            // visually indicate that the retry sequence is being executed.
            const $retry_connection_button = $banner.find(".retry-connection");
            buttons.show_button_loading_indicator($retry_connection_button);
        }
        $banner_label.text(get_connection_error_label(retry_delay_secs));
    }, 1000);
};

// Show user a banner with a button to allow user to navigate
// to the first unread if required.
const FOUND_MISSING_UNREADS_IN_CURRENT_NARROW: Banner = {
    intent: "warning",
    label: $t({
        defaultMessage:
            "This conversation also has older unread messages. Jump to first unread message?",
    }),
    buttons: [
        {
            attention: "quiet",
            label: $t({defaultMessage: "Jump"}),
            custom_classes: "found-missing-unreads-jump-to-first-unread",
        },
    ],
    close_button: true,
    custom_classes: "found-missing-unreads popup-banner",
};

const reloading_application_banner = (reason: ReloadingReason): Banner => {
    let label = $t({defaultMessage: "Reloading…"});
    if (reason === "update") {
        label = $t({
            defaultMessage: "The application has been updated; Reloading…",
        });
    }
    return {
        intent: "info",
        label,
        buttons: [],
        close_button: false,
        custom_classes: "reloading-application popup-banner",
    };
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

function retry_connection_click_handler(e: JQuery.ClickEvent, on_retry_callback: () => void): void {
    e.preventDefault();
    e.stopPropagation();

    const $banner = $(e.currentTarget).closest(".banner");
    $banner
        .find(".banner-label")
        .text($t({defaultMessage: "Unable to connect to Zulip. Trying to reconnect soon…"}));

    const $button = $(e.currentTarget).closest(".retry-connection");

    // If the loading indicator is already being shown, this logic
    // allows us to visually indicate that the retry sequence was
    // executed again by showing the loading indicator on click.
    $button.removeClass("button-hide-loading-indicator-on-hover");
    $button.one("mouseleave", () => {
        $button.addClass("button-hide-loading-indicator-on-hover");
    });

    buttons.show_button_loading_indicator($button);
    on_retry_callback();
}

export function open_connection_error_popup_banner(opts: {
    caller: "server_events" | "message_fetch";
    retry_delay_secs: number;
    on_retry_callback: () => void;
}): void {
    opts.retry_delay_secs = Math.round(opts.retry_delay_secs);
    const retry_connection_attached_click_handler = (e: JQuery.ClickEvent): void => {
        retry_connection_click_handler(e, opts.on_retry_callback);
    };
    // If the banner is already open, don't open it again, and instead remove
    // the loading indicator on the retry button, if it was being shown.
    let $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    if ($banner.length > 0) {
        if ($banner.attr("data-caller") !== opts.caller) {
            // Only the original caller should be able to modify the banner.
            // This prevents the interference between the server errors from
            // get_events in web/src/server_events.js and the one from
            // load_messages in web/src/message_fetch.ts.
            return;
        }
        update_connection_error_banner($banner, opts.retry_delay_secs);
        const $retry_connection_button = $banner.find(".retry-connection");
        if ($retry_connection_button.find(".button-loading-indicator").length > 0) {
            // Add some delay before hiding the loading indicator, to visually
            // indicate that the retry sequence was executed again but failed.
            setTimeout(() => {
                buttons.hide_button_loading_indicator($retry_connection_button);
            }, 1000);
        }
        // Update the click handler to the new on_retry_callback.
        // Remove any click events on the button.
        $retry_connection_button.off("click");
        $retry_connection_button.on("click", retry_connection_attached_click_handler);
        return;
    }

    banners.append(
        connection_error_popup_banner(opts.retry_delay_secs),
        $("#popup_banners_wrapper"),
    );

    $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    if (opts.caller === "server_events") {
        $banner.attr("data-caller", "server_events");
    } else if (opts.caller === "message_fetch") {
        $banner.attr("data-caller", "message_fetch");
    }

    update_connection_error_banner($banner, opts.retry_delay_secs);

    $("#popup_banners_wrapper").on(
        "click",
        ".retry-connection",
        retry_connection_attached_click_handler,
    );
}

export function close_connection_error_popup_banner(
    caller: "server_events" | "message_fetch",
): void {
    const $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    if ($banner.length === 0) {
        return;
    }
    if ($banner.attr("data-caller") !== caller) {
        // Only the original caller should be able to modify the banner.
        return;
    }
    if (retry_connection_interval !== undefined) {
        clearInterval(retry_connection_interval);
    }
    fade_out_popup_banner($banner);
}

export function open_reloading_application_banner(reason: ReloadingReason): void {
    const $banner = $("#popup_banners_wrapper").find(".reloading-application");
    if ($banner.length > 0) {
        // If the banner is already open, don't open it again.
        return;
    }
    banners.append(reloading_application_banner(reason), $("#popup_banners_wrapper"));
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
