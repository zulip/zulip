import $ from "jquery";

import {localstorage} from "./localstorage";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import {user_settings} from "./user_settings";

export function enable(): void {
    $(":root").removeClass("color-scheme-automatic").addClass("dark-theme");

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "dark");
        user_settings.color_scheme = settings_config.color_scheme_values.night.code;
    }
}

export function disable(): void {
    $(":root").removeClass("color-scheme-automatic").removeClass("dark-theme");

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "light");
        user_settings.color_scheme = settings_config.color_scheme_values.day.code;
    }
}

export function default_preference_checker(): void {
    $(":root").removeClass("dark-theme").addClass("color-scheme-automatic");
}
