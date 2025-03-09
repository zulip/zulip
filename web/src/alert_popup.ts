import $ from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import {$t} from "./i18n.ts";

// Show user a banner with a button to allow user to navigate
// to the first unread if required.
const FOUND_MISSING_UNREADS_IN_CURRENT_NARROW: Banner = {
    intent: "warning",
    label: $t({
        defaultMessage: "This conversation also has older unread messages.",
    }),
    buttons: [
        {
            type: "quiet",
            label: $t({defaultMessage: "Jump to first unread"}),
            custom_classes: "found-missing-unreads-jump-to-first-unread",
        },
    ],
    close_button: true,
    custom_classes: "found-missing-unreads popup-alert-banner",
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
            banners.close($banner);
            on_jump_to_first_unread();
        },
    );
}

export function close_found_missing_unreads_banner(): void {
    const $banner = $("#popup_banners_wrapper").find(".found-missing-unreads");
    banners.close($banner);
}

// this will hide the alerts that you click "x" on.
$("body").on("click", ".alert-box > div .exit", function () {
    const $alert = $(this).closest(".alert-box > div");
    $alert.addClass("fade-out");
    setTimeout(() => {
        $alert.removeClass("fade-out show");
    }, 300);
});

$(".alert-box").on("click", ".stackframe", function () {
    $(this).siblings(".code-context").toggle("fast");
});
