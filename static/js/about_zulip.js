import $ from "jquery";

import render_about_zulip from "../templates/about_zulip.hbs";

import * as browser_history from "./browser_history";
import * as copy_button_widget from "./copy_button_widget";
import {$t} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";

export function launch() {
    overlays.open_overlay({
        name: "about-zulip",
        overlay: $("#about-zulip"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    $("#about-zulip .fa-copy").each(function () {
        copy_button_widget.show({
            element: $(this),
            placement: "right",
            content: $t({defaultMessage: "Copy version"}),
        });
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
