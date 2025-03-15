import $ from "jquery";
import assert from "minimalistic-assert";

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
    fade_out_popup_banner($banner);
}

function get_connection_error_popup_banner_label(seconds: number): string {
    seconds = Math.round(seconds);
    if (seconds === 0) {
        return $t({defaultMessage: "Unable to connect to Zulip. Retrying now..."});
    }
    return $t(
        {
            defaultMessage:
                "{seconds, plural, one {Unable to connect to Zulip. Trying again in {seconds} second...} other {Unable to connect to Zulip. Trying again in {seconds} seconds...}}",
        },
        {
            seconds,
        },
    );
}

function make_connection_error_popup_banner(seconds: number): Banner {
    return {
        intent: "danger",
        label: get_connection_error_popup_banner_label(seconds),
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
}

export type ConnectionErrorPopupBannerOpener = "server_events" | "message_fetch";
let connection_error_banner_state:
    | {
          opened: false;
      }
    | {
          opened: true;
          // The opener gets to control the lifecycle of the banner.
          opener: ConnectionErrorPopupBannerOpener;
          retry_seconds: number;
          label_updater_id: ReturnType<typeof setInterval>;
      } = {opened: false};

export function open_connection_error_popup_banner(
    opener: ConnectionErrorPopupBannerOpener,
    opts: {
        on_retry_callback: () => void;
        retry_seconds: number;
    },
): void {
    if (connection_error_banner_state.opened) {
        if (connection_error_banner_state.opener !== opener) {
            // The banner has already been opened by the other code path.
            // We will ignore this request.
            return;
        }
        // The original opener is trying to open the banner again,
        // meaning that this is after a retry. In this case, we remove
        // the loading indicator on the retry button if it was being shown
        // and also update its label text.
        const $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
        assert($banner.length > 0);
        const $retry_connection_button = $banner.find(".retry-connection");
        if ($retry_connection_button.find(".button-loading-indicator").length === 0) {
            // This retry was not due to a button click, so we show
            // the loading indicator ourselves.
            buttons.show_button_loading_indicator($retry_connection_button);
        }
        // Add some delay before hiding the loading indicator, to visually
        // indicate that the retry sequence was executed again but failed.
        setTimeout(() => {
            buttons.hide_button_loading_indicator($retry_connection_button);
        }, 1000);
        connection_error_banner_state.retry_seconds = opts.retry_seconds;
        clearInterval(connection_error_banner_state.label_updater_id);
        const $label = $banner.find(".banner-label");
        $label.text(get_connection_error_popup_banner_label(0));
        connection_error_banner_state.label_updater_id = setInterval(
            connection_error_popup_banner_label_updater,
            1000,
        );
        return;
    }
    // Open the banner.
    connection_error_banner_state = {
        opened: true,
        opener,
        retry_seconds: opts.retry_seconds,
        label_updater_id: setInterval(connection_error_popup_banner_label_updater, 1000),
    };
    const banner = make_connection_error_popup_banner(opts.retry_seconds);
    banners.append(banner, $("#popup_banners_wrapper"));

    $("#popup_banners_wrapper").on("click", ".retry-connection", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();

        buttons.show_button_loading_indicator($(this));
        opts.on_retry_callback();
    });
}

function connection_error_popup_banner_label_updater(): void {
    const $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    assert(connection_error_banner_state.opened);
    if ($banner.length === 0) {
        // The banner was probably closed by the user.
        clearInterval(connection_error_banner_state.label_updater_id);
        connection_error_banner_state = {opened: false};
        return;
    }
    const $label = $banner.find(".banner-label");
    connection_error_banner_state.retry_seconds -= 1;
    $label.text(
        get_connection_error_popup_banner_label(connection_error_banner_state.retry_seconds),
    );
    if (connection_error_banner_state.retry_seconds === 1) {
        clearInterval(connection_error_banner_state.label_updater_id);
    }
}

export function close_connection_error_popup_banner(
    opener: ConnectionErrorPopupBannerOpener,
): void {
    if (!connection_error_banner_state.opened || connection_error_banner_state.opener !== opener) {
        // The command to close the banner should come only
        // from the code path that got to opened it.
        return;
    }
    const $banner = $("#popup_banners_wrapper").find(".connection-error-banner");
    // Even if the banner was closed by the user, we don't need to do anything different.
    fade_out_popup_banner($banner);
    clearInterval(connection_error_banner_state.label_updater_id);
    connection_error_banner_state = {opened: false};
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
