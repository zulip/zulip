import $ from "jquery";

import render_deprecated_feature_notice from "../templates/deprecated_feature_notice.hbs";

import * as blueslip from "./blueslip";
import * as common from "./common";
import {$t} from "./i18n";
import {localstorage} from "./localstorage";
import * as overlays from "./overlays";

export function get_hotkey_deprecation_notice(originalHotkey, replacementHotkey) {
    return $t(
        {
            defaultMessage:
                'We\'ve replaced the "{originalHotkey}" hotkey with "{replacementHotkey}" to make this common shortcut easier to trigger.',
        },
        {originalHotkey, replacementHotkey},
    );
}

let shown_deprecation_notices = [];

export function maybe_show_deprecation_notice(key) {
    let message;
    const isCmdOrCtrl = common.has_mac_keyboard() ? "Cmd" : "Ctrl";
    if (key === "C") {
        message = get_hotkey_deprecation_notice("C", "x");
    } else if (key === "*") {
        message = get_hotkey_deprecation_notice("*", isCmdOrCtrl + " + s");
    } else {
        blueslip.error("Unexpected deprecation notice for hotkey:", key);
        return;
    }

    // Here we handle the tracking for showing deprecation notices,
    // whether or not local storage is available.
    if (localstorage.supported()) {
        const notices_from_storage = JSON.parse(localStorage.getItem("shown_deprecation_notices"));
        if (notices_from_storage !== null) {
            shown_deprecation_notices = notices_from_storage;
        } else {
            shown_deprecation_notices = [];
        }
    }

    if (!shown_deprecation_notices.includes(key)) {
        const rendered_deprecated_feature_notice = render_deprecated_feature_notice({message});
        const deprecated_feature_notice = $(rendered_deprecated_feature_notice);

        $(".app").append(deprecated_feature_notice);

        overlays.open_modal("#deprecation-notice-modal", {autoremove: true});
        $("#deprecation-notice-message").text(message);
        $("#close-deprecation-notice").trigger("focus");
        shown_deprecation_notices.push(key);
        if (localstorage.supported()) {
            localStorage.setItem(
                "shown_deprecation_notices",
                JSON.stringify(shown_deprecation_notices),
            );
        }
    }
}
