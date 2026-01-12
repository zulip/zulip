import $ from "jquery";

import static_favicon_image from "../../static/images/favicon.svg";
import render_favicon_svg from "../templates/favicon.svg.hbs";

import * as blueslip from "./blueslip.ts";
import favicon_font_url_html from "./favicon_font_url!=!url-loader!font-subset-loader2?glyphs=0123456789KMGT∞!source-sans/TTF/SourceSans3-Bold.ttf"; // eslint-disable-line import/extensions
import {page_params} from "./page_params.ts";

let favicon_state: {image: HTMLImageElement; url: string} | undefined;

function load_and_set_favicon(rendered_favicon: string): void {
    favicon_state = {
        url: URL.createObjectURL(new Blob([rendered_favicon], {type: "image/svg+xml"})),
        image: new Image(),
    };

    favicon_state.image.src = favicon_state.url;
    favicon_state.image.addEventListener("load", set_favicon);
}

function set_favicon(): void {
    if (favicon_state === undefined) {
        throw new Error("Programming error: favicon_state must be set.");
    }
    $("#favicon").attr("href", favicon_state.url);
}

export function update_favicon(new_message_count: number, pm_count: number): void {
    try {
        // If the app is still loading, force the static icon and stop.
        // We use bracket notation to satisfy the TypeScript index signature rule.
        if (page_params["is_loading"]) {
            $("#favicon").attr("href", static_favicon_image);
            return;
        }

        if (favicon_state !== undefined) {
            favicon_state.image.removeEventListener("load", set_favicon);
            favicon_state.image.src = "data:,";
            URL.revokeObjectURL(favicon_state.url);
            favicon_state = undefined;
        }

        if (new_message_count === 0 && pm_count === 0) {
            $("#favicon").attr("href", static_favicon_image);
            return;
        }

        const pow = Math.floor(Math.log10(new_message_count) / 3);
        const suffix = ["", "K", "M", "G", "T"][pow];
        const count =
            new_message_count === 0
                ? ""
                : pow < 5
                  ? `${Math.floor(new_message_count / 1e3 ** pow)}${suffix}`
                  : "∞";
        const count_long = count.length > 2;
        const rendered_favicon = render_favicon_svg({
            count,
            count_long,
            have_pm: pm_count !== 0,
            favicon_font_url_html,
        });

        load_and_set_favicon(rendered_favicon);
    } catch (error) {
        blueslip.error("Failed to update favicon", undefined, error);
    }
}
