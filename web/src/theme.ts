import $ from "jquery";

import {localstorage} from "./localstorage.ts";
import * as message_lists from "./message_lists.ts";
import * as realm_logo from "./realm_logo.ts";
import * as settings_config from "./settings_config.ts";
import {user_settings} from "./user_settings.ts";

const ls = localstorage();

function set_dark_theme(): void {
    $(":root").removeClass("color-scheme-automatic").addClass("dark-theme");
}

function set_light_theme(): void {
    $(":root").removeClass("color-scheme-automatic").removeClass("dark-theme");
}

function set_automatic_theme(): void {
    $(":root").removeClass("dark-theme").addClass("color-scheme-automatic");
}

export function set_theme(color_scheme: number): void {
    if (color_scheme === settings_config.color_scheme_values.dark.code) {
        set_dark_theme();
    } else if (color_scheme === settings_config.color_scheme_values.light.code) {
        set_light_theme();
    } else {
        // If the color_scheme_code is not valid, fallback to automatic.
        set_automatic_theme();
    }
}

export function set_theme_and_update(color_scheme: number): void {
    set_theme(color_scheme);
    // We cannot update recipient bar color and the realm logo variant
    // using `set_theme` since that function is being called in the
    // `ui_init` module before message_lists and realm_logo are initialized
    // and the order cannot be changed.
    message_lists.update_recipient_bar_background_color();
    realm_logo.render();
}

function get_theme_for_spectator(): number {
    // If the spectator has not set a theme preference, fallback to automatic.
    return (
        Number(ls.get("spectator-theme-preference")) ||
        settings_config.color_scheme_values.automatic.code
    );
}

export function set_theme_for_spectator(color_scheme: number): void {
    // Since we don't have events for spectators and handle the theme using
    // localstorage, the theme change does not reflect across tabs.
    ls.set("spectator-theme-preference", color_scheme);
    user_settings.color_scheme = color_scheme;
    set_theme_and_update(color_scheme);
}

export function initialize_theme_for_spectator(): void {
    const color_scheme = get_theme_for_spectator();
    user_settings.color_scheme = color_scheme;
    set_theme(color_scheme);
}
