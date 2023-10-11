import $ from "jquery";

import * as components from "./components";
import {$t} from "./i18n";

export let toggler: components.Toggle;
export let select_tab = "personal_settings";

export function setup_toggler(): void {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "General"}), key: "general_settings"},
            {label: $t({defaultMessage: "Personal"}), key: "personal_settings"},
            {label: $t({defaultMessage: "Subscribers"}), key: "subscriber_settings"},
        ],
        callback(_name, key) {
            $(".stream_section").hide();
            $(`.${CSS.escape(key)}`).show();
            select_tab = key;
        },
    });
}
