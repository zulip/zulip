if (window.electron_bridge !== undefined) {
    window.electron_bridge.on_event("logout", () => {
        $("#logout_form").trigger("submit");
    });

    window.electron_bridge.on_event("show-keyboard-shortcuts", () => {
        hashchange.go_to_location("keyboard-shortcuts");
    });

    window.electron_bridge.on_event("show-notification-settings", () => {
        hashchange.go_to_location("settings/notifications");
    });
}

export {};
