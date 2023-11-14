import $ from "jquery";

import * as components from "./components";
import {$t} from "./i18n";

export let toggler: components.Toggle;
export let select_tab = "personal";

export function setup_toggler(): void {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "General"}), key: "general"},
            {label: $t({defaultMessage: "Personal"}), key: "personal"},
            {label: $t({defaultMessage: "Subscribers"}), key: "subscribers"},
        ],
        callback(_name, key) {
            $(".stream_section").hide();
            $(`[data-stream-section="${CSS.escape(key)}"]`).show();
            select_tab = key;
        },
    });
}
