import $ from "jquery";

import loading_black_image from "../../static/images/loading/loader-black.svg";
import loading_white_image from "../../static/images/loading/loader-white.svg";
import render_loader from "../templates/loader.hbs";

export function make_indicator(
    $outer_container: JQuery,
    {
        abs_positioned = false,
        text,
        width,
        height,
    }: {
        abs_positioned?: boolean;
        text?: string;
        width?: number | undefined;
        height?: number | undefined;
    } = {},
): void {
    let $container = $outer_container;
    // The pixel values here were established under a 14px
    // font-size, so we convert the values to ems using
    // this value
    const legacy_em_in_px = 14;

    // TODO: We set white-space to 'nowrap' because under some
    // unknown circumstances (it happens on Keegan's laptop) the text
    // width calculation, above, returns a result that's a few pixels
    // too small.  The container's div will be slightly too small,
    // but that's probably OK for our purposes.
    $outer_container.css({"white-space": "nowrap"});

    $container.empty();

    if (abs_positioned) {
        // Create some additional containers to facilitate absolutely
        // positioned spinners.
        const container_id = $container.attr("id")!;
        let $inner_container = $("<div>").attr("id", `${container_id}_box_container`);
        $container.append($inner_container);
        $container = $inner_container;
        $inner_container = $("<div>").attr("id", `${container_id}_box`);
        $container.append($inner_container);
        $container = $inner_container;
    }

    const $spinner_elem = $("<div>")
        .addClass("loading_indicator_spinner")
        .attr("aria-hidden", "true");
    $spinner_elem.html(render_loader({container_id: $outer_container.attr("id")}));
    $container.append($spinner_elem);
    let text_width = 0;

    if (text !== undefined) {
        const $text_elem = $("<span>").addClass("loading_indicator_text");
        $text_elem.text(text);
        $container.append($text_elem);
        // See note, below
        if (!abs_positioned) {
            text_width = 20 + ($text_elem.width() ?? 0);
        }
    }

    // These width calculations are tied to the spinner width and
    // margins defined via CSS
    if (width !== undefined) {
        $container.css({width: `${(width + text_width) / legacy_em_in_px}em`});
    } else {
        $container.css({width: `${(38 + text_width) / legacy_em_in_px}em`});
    }
    if (height !== undefined) {
        $container.css({height});
    } else {
        $container.css({height: 0});
    }

    $outer_container.data("destroying", false);
}

export function destroy_indicator($container: JQuery): void {
    if ($container.data("destroying")) {
        return;
    }
    $container.data("destroying", true);
    $container.empty();
    $container.css({width: 0, height: 0});
}

export function show_button_spinner($elt: JQuery, using_dark_theme: boolean): void {
    if (!using_dark_theme) {
        $elt.attr("src", loading_black_image);
    } else {
        $elt.attr("src", loading_white_image);
    }
    $elt.css("display", "inline-block");
}

export function show_spinner($button_element: JQuery, $spinner: JQuery): void {
    const span_width = $button_element.find(".submit-button-text").width();
    const span_height = $button_element.find(".submit-button-text").height();

    // Hide the submit button after computing its height, since submit
    // buttons with long text might affect the size of the button.
    $button_element.find(".submit-button-text").hide();

    // Create the loading indicator
    make_indicator($spinner, {
        width: span_width,
        height: span_height,
    });
}

export function hide_spinner($button_element: JQuery, $spinner: JQuery): void {
    // Show the span
    $button_element.find(".submit-button-text").show();

    // Destroy the loading indicator
    destroy_indicator($spinner);
}
