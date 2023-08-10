import ClipboardJS from "clipboard";
import $ from "jquery";

import render_about_zulip from "../templates/about_zulip.hbs";

import * as browser_history from "./browser_history";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import {show_copied_confirmation} from "./tippyjs";

export function launch() {
    overlays.open_overlay({
        name: "about-zulip",
        $overlay: $("#about-zulip"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    const clipboard = new ClipboardJS("#about-zulip .fa-copy");

    clipboard.on("success", () => {
        show_copied_confirmation($("#about-zulip .fa-copy")[0]);
    });
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
}
