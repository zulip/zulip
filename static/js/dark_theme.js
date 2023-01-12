import $ from "jquery";

import {localstorage} from "./localstorage";
import {page_params} from "./page_params";

export function enable() {
    $(":root").removeClass("color-scheme-automatic").addClass("dark-theme");

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "dark");
    }
}

export function disable() {
    $(":root").removeClass("color-scheme-automatic").removeClass("dark-theme");

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "light");
    }
}

export function default_preference_checker() {
    $(":root").removeClass("dark-theme").addClass("color-scheme-automatic");
}
