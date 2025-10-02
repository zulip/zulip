import $ from "jquery";

import * as loading from "./loading.ts";
import {COMPONENT_INTENT_VALUES} from "./types.ts";
import type {ComponentIntent} from "./types.ts";

export const ACTION_BUTTON_ATTENTION_VALUES = ["primary", "quiet", "borderless"] as const;

export type ActionButtonAttention = (typeof ACTION_BUTTON_ATTENTION_VALUES)[number];

export type ActionButton = {
    attention: ActionButtonAttention;
    intent?: ComponentIntent;
    label: string;
    icon?: string;
    custom_classes?: string;
};

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

export function modify_action_button_style(
    $button: JQuery,
    opts: {
        attention?: ActionButtonAttention;
        intent?: ComponentIntent;
    },
): void {
    if (opts.attention === undefined && opts.intent === undefined) {
        // If neither attention nor intent is provided, do nothing.
        return;
    }
    const action_button_attention_pattern = ACTION_BUTTON_ATTENTION_VALUES.join("|");
    const component_intent_pattern = COMPONENT_INTENT_VALUES.join("|");
    const action_button_style_regex = new RegExp(
        `action-button-(${action_button_attention_pattern})-(${component_intent_pattern})`,
    );
    const action_button_style_regex_match = $button.attr("class")?.match(action_button_style_regex);
    if (!action_button_style_regex_match) {
        // If the button doesn't have the expected class, do nothing.
        return;
    }
    const [action_button_style_class, old_attention, old_intent] = action_button_style_regex_match;
    // Replace the old attention and intent values with the new ones, if provided.
    $button.removeClass(action_button_style_class);
    $button.addClass(
        `action-button-${opts.attention ?? old_attention}-${opts.intent ?? old_intent}`,
    );
}
