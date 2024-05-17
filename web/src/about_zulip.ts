import ClipboardJS from "clipboard";
import $ from "jquery";

import render_about_zulip from "../templates/about_zulip.hbs";

import * as browser_history from "./browser_history";
import {show_copied_confirmation} from "./copied_tooltip";
import * as overlays from "./overlays";
import {realm} from "./state_data";

export function launch(): void {
    overlays.open_overlay({
        name: "about-zulip",
        $overlay: $("#about-zulip"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    const zulip_version_clipboard = new ClipboardJS("#about-zulip .fa-copy.zulip-version");
    zulip_version_clipboard.on("success", () => {
        show_copied_confirmation($("#about-zulip .fa-copy.zulip-version")[0]);
    });

    const zulip_merge_base_clipboard = new ClipboardJS("#about-zulip .fa-copy.zulip-merge-base");
    zulip_merge_base_clipboard.on("success", () => {
        show_copied_confirmation($("#about-zulip .fa-copy.zulip-merge-base")[0]);
    });
}

export function initialize(): void {
    const rendered_about_zulip = render_about_zulip({
        zulip_version: realm.zulip_version,
        zulip_merge_base: realm.zulip_merge_base,
        is_fork: realm.zulip_merge_base && realm.zulip_merge_base !== realm.zulip_version,
    });
    $("#about-zulip-modal-container").append($(rendered_about_zulip));
}
