import $ from "jquery";

import render_gif_picker_ui from "../templates/gif_picker_ui.hbs";
import render_giphy_footer from "../templates/giphy_footer.hbs";

import type {GifProvider} from "./abstract_gif_network.ts";
import {$t} from "./i18n.ts";
import {the} from "./util.ts";

export function get_gif_popover_content(provider: GifProvider): HTMLElement {
    const $picker = $(render_gif_picker_ui());
    if (provider === "giphy") {
        $picker.find("#gif-search-query").attr("placeholder", $t({defaultMessage: "Filter"}));

        // We are required to include the
        // "Powered By GIPHY" banner, which isn't mandatory
        // for Tenor. So we avoid including one for Tenor
        // to save space.
        $picker.find(".popover-inner").append($(render_giphy_footer()));
    } else {
        $picker.find("#gif-search-query").attr("placeholder", $t({defaultMessage: "Search Tenor"}));
    }
    return the<HTMLElement>($picker);
}
