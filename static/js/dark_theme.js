import $ from "jquery";

import * as floating_recipient_bar from "./floating_recipient_bar";
import {localstorage} from "./localstorage";
import * as message_lists from "./message_lists";
import {page_params} from "./page_params";


export function enable() {
    $(":root").removeClass("color-scheme-automatic").addClass("dark-theme");
    if (message_lists.current) {
        message_lists.current.view.rerender_preserving_scrolltop();
        floating_recipient_bar.update();
    }

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "dark");
    }
}

export function disable() {
    $(":root").removeClass("color-scheme-automatic").removeClass("dark-theme");
    if (message_lists.current) {
        message_lists.current.view.rerender_preserving_scrolltop();
        floating_recipient_bar.update();
    }

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "light");
    }
}

export function default_preference_checker() {
    $(":root").removeClass("dark-theme").addClass("color-scheme-automatic");
}
