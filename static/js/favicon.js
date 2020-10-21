import render_favicon_svg from "../templates/favicon.svg.hbs";

import favicon_font_url from "!url-loader!font-subset-loader2?glyphs=0123456789KMGT∞!source-sans-pro/TTF/SourceSansPro-Bold.ttf";

let favicon_url;

export function set(url) {
    $("#favicon").attr("href", url);
}

export function update_favicon(new_message_count, pm_count) {
    if (new_message_count === 0 && pm_count === 0) {
        $("#favicon").attr("href", "/static/images/favicon.svg?v=4");
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
        favicon_font_url,
    });

    if (favicon_url !== undefined) {
        URL.revokeObjectURL(favicon_url);
    }
    favicon_url = URL.createObjectURL(new Blob([rendered_favicon], {type: "image/svg+xml"}));

    // Without loading the SVG in an Image first, Chrome mysteriously fails to
    // render the webfont (https://crbug.com/1140920).
    const image = new Image();
    image.src = favicon_url;
    image.addEventListener("load", () => {
        $("#favicon").attr("href", favicon_url);
    });
}
