import $ from "jquery";

import * as loading from "./loading.ts";

export function show_button_loading_indicator($button: JQuery): void {
    // If the button already has a loading indicator, do nothing.
    if ($button.find(".button-loading-indicator").length > 0) {
        return;
    }
    // First, we disable the button and hide its contents.
    $button.prop("disabled", true);
    $button.find(".zulip-icon").css("visibility", "hidden");
    $button.find(".action-button-label").css("visibility", "hidden");
    // Next, we create a loading indicator with a unique id.
    // The unique id is required for the `filter` element in the loader SVG,
    // to prevent the loading indicator from being hidden due to duplicate ids.
    // Reference commit: 995d073dbfd8f22a2ef50c1320e3b1492fd28649
    const loading_indicator_unique_id = `button-loading-indicator-${Date.now()}`;
    const $button_loading_indicator = $("<span>")
        .attr("id", loading_indicator_unique_id)
        .addClass("button-loading-indicator");
    $button.append($button_loading_indicator);
    loading.make_indicator($button_loading_indicator, {
        width: $button.width(),
        height: $button.height(),
    });
}

export function hide_button_loading_indicator($button: JQuery): void {
    $button.find(".button-loading-indicator").remove();
    $button.prop("disabled", false);
    $button.find(".zulip-icon").css("visibility", "visible");
    $button.find(".action-button-label").css("visibility", "visible");
}
