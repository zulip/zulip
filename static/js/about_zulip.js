import ClipboardJS from "clipboard";
import $ from "jquery";

import * as browser_history from "./browser_history";
import * as overlays from "./overlays";

export function launch() {
    overlays.open_overlay({
        name: "about-zulip",
        overlay: $("#about-zulip"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    new ClipboardJS("#about-zulip .fa-copy");
}
