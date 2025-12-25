import $ from "jquery";
import type * as tippy from "tippy.js";

import render_gif_picker_ui from "../templates/gif_picker_ui.hbs";
import render_giphy_footer from "../templates/giphy_footer.hbs";

import {$t} from "./i18n.ts";
import * as ui_util from "./ui_util.ts";

export function populate_gif_popover(instance: tippy.Instance, is_giphy: boolean): void {
    const html = render_gif_picker_ui();
    instance.setContent(ui_util.parse_html(html));
    const $popper = $(instance.popper);
    if (is_giphy) {
        $popper.find("#gif-search-query").attr("placeholder", $t({defaultMessage: "Filter"}));

        // We are required to include the
        // "Powered By GIPHY" banner, which isn't mandatory
        // for Tenor. So we avoid including one for Tenor
        // to save space.
        $popper.find(".popover-inner").append($(render_giphy_footer()));
    } else {
        $popper.find("#gif-search-query").attr("placeholder", $t({defaultMessage: "Search Tenor"}));
    }
}
