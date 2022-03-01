import $ from "jquery";

import {$t} from "./i18n";

export function show_copied_confirmation(copy_button, clipboard) {
    const $alert_msg = $(copy_button).closest(".message_row").find(".alert-msg");
    clipboard.on("success", () => {
        $alert_msg.text($t({defaultMessage: "Copied!"}));
        $alert_msg.css("display", "block");
        $alert_msg.addClass("copied");
        $alert_msg.delay(1000).fadeOut(300, function () {
            $(this).removeClass("copied");
        });
        if ($(".tooltip").is(":visible")) {
            $(".tooltip").hide();
        }
    });
}
