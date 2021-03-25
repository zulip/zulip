import $ from "jquery";

import * as browser_history from "./browser_history";

if (window.electron_bridge !== undefined) {
    window.electron_bridge.on_event("logout", () => {
        $("#logout_form").trigger("submit");
    });

    window.electron_bridge.on_event("show-keyboard-shortcuts", () => {
        browser_history.go_to_location("keyboard-shortcuts");
    });

    window.electron_bridge.on_event("show-notification-settings", () => {
        browser_history.go_to_location("settings/notifications");
    });
}
