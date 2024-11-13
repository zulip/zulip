import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_about_zulip from "../templates/about_zulip.hbs";

import * as browser_history from "./browser_history.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as overlays from "./overlays.ts";
import {realm} from "./state_data.ts";

export function launch(): void {
    overlays.open_overlay({
        name: "about-zulip",
        $overlay: $("#about-zulip"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    const zulip_version_clipboard = new ClipboardJS("#about-zulip .zulip-version");
    zulip_version_clipboard.on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });

    const zulip_merge_base_clipboard = new ClipboardJS("#about-zulip .zulip-merge-base");
    zulip_merge_base_clipboard.on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
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
