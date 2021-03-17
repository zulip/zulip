export function launch() {
    overlays.open_overlay({
        name: "about-zulip",
        overlay: $("#about-zulip"),
        on_close() {
            hashchange.exit_overlay();
        },
    });
}
