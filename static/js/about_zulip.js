import ClipboardJS from "clipboard";
import $ from "jquery";
import tippy from "tippy.js";

import render_about_zulip from "../templates/about_zulip.hbs";

import * as browser_history from "./browser_history";
import {$t} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";

export function launch() {
    overlays.open_overlay({
        name: "about-zulip",
        $overlay: $("#about-zulip"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    new ClipboardJS("#about-zulip .fa-copy");
}

export function initialize() {
    const rendered_about_zulip = render_about_zulip({
        zulip_version: page_params.zulip_version,
        zulip_merge_base: page_params.zulip_merge_base,
        is_fork:
            page_params.zulip_merge_base &&
            page_params.zulip_merge_base !== page_params.zulip_version,
    });
    $(".app").append(rendered_about_zulip);

    $("#about-zulip i.tippy-zulip-tooltip").on("click", (event) => {
        show_tooltip($(event.target));
    });
}

export function show_tooltip(element) {
    // Display a tooltip to notify the user the version was copied.
    const instance = tippy("#about-zulip i.tippy-zulip-tooltip", {
        onUntrigger() {
            remove_instance();
        },
    }).find((tippy) => tippy.id === element[0]._tippy.id);
    instance.setContent($t({defaultMessage: "Copied!"}));
    instance.show();
    function remove_instance() {
        if (!instance.state.isDestroyed) {
            instance.destroy();
        }
    }
    setTimeout(remove_instance, 3000);
}
