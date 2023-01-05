import $ from "jquery";

import render_favicon_svg from "../templates/favicon.svg.hbs";

import * as blueslip from "./blueslip";
import favicon_font_url from "./favicon_font_url!=!url-loader!font-subset-loader2?glyphs=0123456789KMGT∞!source-sans/TTF/SourceSans3-Bold.ttf";
import {page_params} from "./page_params";
import {user_settings} from "./user_settings";

let favicon_state;
let favicon_change_retries = 0;
let icon_data_url = "";
let current_counts = {new_message_count:0, pm_count:0};
let fetching_image = false;

function load_and_set_favicon(rendered_favicon) {
    favicon_state = {
        url: URL.createObjectURL(new Blob([rendered_favicon], {type: "image/svg+xml"})),
        image: new Image(),
    };

    // Without loading the SVG in an Image first, Chrome mysteriously fails to
    // render the webfont (https://crbug.com/1140920).
    favicon_state.image.src = favicon_state.url;
    favicon_state.image.addEventListener("load", set_favicon);
}

function set_favicon() {
    $("#favicon").attr("href", favicon_state.url);
}

export function update_attrs_and_alt_icon() {
    if (user_settings.realm_icon_as_favicon && page_params.realm_icon_url) {
        $("#alternate_icon").attr("href", page_params.realm_icon_url);
        $("#favicon").attr("sizes", "any");
        $("#alternate_icon").attr("sizes", "any");
    } else {
        $("#alternate_icon").attr("href", "/static/images/favicon.png?v=4");
        $("#favicon").removeAttr("sizes");
        $("#alternate_icon").removeAttr("sizes");
    }
}

export function update_favicon(new_message_count, pm_count) {
    current_counts = {new_message_count, pm_count};
    try {
        if (favicon_state !== undefined) {
            favicon_state.image.removeEventListener("load", set_favicon);

            // We need to remove this src so revokeObjectURL doesn't cause a
            // net::ERR_FILE_NOT_FOUND error in Chrome. This seems to be the
            // simplest way to do that without triggering an expensive network
            // request or spewing a different console error.
            favicon_state.image.src = "data:,";

            URL.revokeObjectURL(favicon_state.url);
            favicon_state = undefined;
        }

        if (new_message_count === 0 && pm_count === 0) {
            if (user_settings.realm_icon_as_favicon && page_params.realm_icon_url) {
                $("#favicon").attr("href", page_params.realm_icon_url);
            } else {
                $("#favicon").attr("href", "/static/images/favicon.svg?v=4");
            }
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

        // if (user_settings.realm_icon_as_favicon) {
        //     // we need to use a data url, we cannot just pass a href into
        //     // the template because we generate an immutable blob (as part
        //     // of a the work around for the above web font bug) from the
        //     // template which would not include the rendered image
        //     icon_data_url = page_params.realm_icon_data_url;
        // }
        const rendered_favicon = render_favicon_svg({
            count,
            count_long,
            have_pm: pm_count !== 0,
            favicon_font_url,
            icon_data_url,
        });
        load_and_set_favicon(rendered_favicon);
    } catch (error) {
        blueslip.error("Failed to update favicon", undefined, error.stack);
    }
}

export async function change_favicon_image() {
    if (fetching_image) {
        console.log("already fetching");
        return;
    }
    if (favicon_change_retries > 3) {
        return;
    }
    if (!user_settings.realm_icon_as_favicon) {
        console.log("not realm_icon_as_favicon");
        icon_data_url = "";
        update_favicon(current_counts.new_message_count, current_counts.pm_count);
        return;
    }
    try {
        fetching_image = true;
        const response = await fetch(page_params.realm_icon_url);
        const reader = new FileReader();
        reader.readAsDataURL(await response.blob());
        await new Promise((resolve) => {
            reader.addEventListener("load", () => {
                resolve();
            });
        });
        fetching_image = false;
        icon_data_url = reader.result;
    } catch {
        fetching_image = false;
        favicon_change_retries += 1;
        change_favicon_image();
        return;
    }
    favicon_change_retries = 0;
    update_favicon(current_counts.new_message_count, current_counts.pm_count);
}