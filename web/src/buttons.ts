import $ from "jquery";

import * as loading from "./loading.ts";

let loading_indicator_count = 0;
export function show_button_loading_indicator($button: JQuery): void {
    // If the button already has a loading indicator, do nothing.
    if ($button.find(".button-loading-indicator").length > 0) {
        return;
    }
    // First, we hide the current content of the button.
    $button.find(".zulip-icon").css("visibility", "hidden");
    $button.find(".action-button-label").css("visibility", "hidden");
    // Next, we create a loading indicator with a unique id.
    // The unique id is required for the `filter` element in the loader SVG,
    // to prevent the loading indicator from being hidden due to duplicate ids.
    // Reference commit: 995d073dbfd8f22a2ef50c1320e3b1492fd28649
    const loading_indicator_unique_id = `button-loading-indicator-${loading_indicator_count}`;
    loading_indicator_count += 1;
    const $button_loading_indicator = $("<span>")
        .attr("id", loading_indicator_unique_id)
        .addClass("button-loading-indicator");
    requestAnimationFrame(() => {
        // We want this to happen in the same animation frame to
        // avoid showing a non spinning loading indicator.
        $button.append($button_loading_indicator);
        loading.make_indicator($button_loading_indicator, {
            width: $button.width(),
            height: $button.height(),
        });
    });
}

export function hide_button_loading_indicator($button: JQuery): void {
    $button.find(".button-loading-indicator").remove();
    $button.prop("disabled", false);
    $button.find(".zulip-icon").css("visibility", "visible");
    $button.find(".action-button-label").css("visibility", "visible");
}
