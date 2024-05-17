import {z} from "zod";

import * as blueslip from "./blueslip";
import * as common from "./common";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import {localstorage} from "./localstorage";

export function get_hotkey_deprecation_notice(
    originalHotkey: string,
    replacementHotkey: string,
): string {
    return $t_html(
        {
            defaultMessage:
                'We\'ve replaced the "{originalHotkey}" hotkey with "{replacementHotkey}" to make this common shortcut easier to trigger.',
        },
        {originalHotkey, replacementHotkey},
    );
}

let shown_deprecation_notices: string[] = [];

export function maybe_show_deprecation_notice(key: string): void {
    let message;
    const isCmdOrCtrl = common.has_mac_keyboard() ? "Cmd" : "Ctrl";
    switch (key) {
        case "Shift + C":
            message = get_hotkey_deprecation_notice("Shift + C", "X");
            break;
        case "*":
            message = get_hotkey_deprecation_notice("*", isCmdOrCtrl + " + S");
            break;
        case "Shift + S":
            message = get_hotkey_deprecation_notice("Shift + S", "S");
            break;
        default:
            blueslip.error("Unexpected deprecation notice for hotkey:", {key});
            return;
    }

    // Here we handle the tracking for showing deprecation notices,
    // whether or not local storage is available.
    if (localstorage.supported()) {
        const notices_from_storage = localStorage.getItem("shown_deprecation_notices");
        if (notices_from_storage !== null) {
            const parsed_notices_from_storage = z
                .array(z.string())
                .parse(JSON.parse(notices_from_storage));

            shown_deprecation_notices = parsed_notices_from_storage;
        } else {
            shown_deprecation_notices = [];
        }
    }

    if (!shown_deprecation_notices.includes(key)) {
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Deprecation notice"}),
            html_body: message,
            html_submit_button: $t_html({defaultMessage: "Got it"}),
            on_click() {
                return;
            },
            close_on_submit: true,
            focus_submit_on_open: true,
            single_footer_button: true,
        });

        shown_deprecation_notices.push(key);
        if (localstorage.supported()) {
            localStorage.setItem(
                "shown_deprecation_notices",
                JSON.stringify(shown_deprecation_notices),
            );
        }
    }
}
