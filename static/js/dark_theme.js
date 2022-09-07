import $ from "jquery";

import {localstorage} from "./localstorage";
import {page_params} from "./page_params";

import * as floating_recipient_bar from "./floating_recipient_bar";
import * as message_lists from "./message_lists";

export function enable() {
    $("body").removeClass("color-scheme-automatic").addClass("dark-theme");
    message_lists.current.view.rerender_preserving_scrolltop();
    floating_recipient_bar.update();

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "dark");
    }
}

export function disable() {
    $("body").removeClass("color-scheme-automatic").removeClass("dark-theme");
    message_lists.current.view.rerender_preserving_scrolltop();
    floating_recipient_bar.update();

    if (page_params.is_spectator) {
        const ls = localstorage();
        ls.set("spectator-theme-preference", "light");
    }
}

export function default_preference_checker() {
    $("body").removeClass("dark-theme").addClass("color-scheme-automatic");
}
